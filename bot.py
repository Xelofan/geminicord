import asyncio
import json
import logging
import os
import re
from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

import aiofiles
import discord
import google.generativeai as genai
from discord import app_commands
from discord.ext import commands
import httpx
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro"]
EDIT_DELAY_SECONDS = 2
MAX_MESSAGE_NODES = 500
SERVER_DATA_DIR = Path("server_data")

# Ensure server data directory exists
SERVER_DATA_DIR.mkdir(exist_ok=True)

# HTTP client for downloading images
httpx_client = httpx.AsyncClient(timeout=30.0)


def get_config(filename: str = "config.yaml") -> dict[str, Any]:
    with open(filename, encoding="utf-8") as file:
        return yaml.safe_load(file)


config = get_config()

# Configure Gemini
genai.configure(api_key=config["gemini_api_key"])

msg_nodes = {}
last_task_time = 0
data_locks = {}  # Locks for each server's data file

intents = discord.Intents.default()
intents.message_content = True
activity = discord.CustomActivity(name=(config.get("status_message") or "Powered by Gemini 2.5")[:128])
discord_bot = commands.Bot(intents=intents, activity=activity, command_prefix=None)


@dataclass
class MsgNode:
    text: Optional[str] = None
    images: list[dict] = field(default_factory=list)  # Proper image parts for Gemini
    role: Literal["user", "model"] = "model"
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    has_bad_attachments: bool = False
    fetch_parent_failed: bool = False
    parent_msg: Optional[discord.Message] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ServerDataManager:
    @staticmethod
    def get_server_file(server_id: Optional[int], user_id: Optional[int] = None) -> Path:
        """Get the JSON file path for a server or DM."""
        if server_id is None:  # DM
            return SERVER_DATA_DIR / f"dm_{user_id}.json"
        return SERVER_DATA_DIR / f"{server_id}.json"

    @staticmethod
    async def get_lock(server_id: Optional[int], user_id: Optional[int] = None) -> asyncio.Lock:
        """Get or create a lock for a server's data file."""
        key = f"dm_{user_id}" if server_id is None else str(server_id)
        if key not in data_locks:
            data_locks[key] = asyncio.Lock()
        return data_locks[key]

    @staticmethod
    async def load_server_data(server_id: Optional[int], user_id: Optional[int] = None) -> dict:
        """Load server data from JSON file."""
        file_path = ServerDataManager.get_server_file(server_id, user_id)
        lock = await ServerDataManager.get_lock(server_id, user_id)

        async with lock:
            if not file_path.exists():
                default_data = {
                    "model": config["default_model"],
                    "system_prompt": config["default_system_prompt"],
                    "users": {} if server_id else None
                }
                if server_id is None:  # DM
                    default_data["user"] = {}
                await ServerDataManager._save_data(file_path, default_data)
                return default_data

            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    return json.loads(content)
            except Exception as e:
                logging.error(f"Error loading server data: {e}")
                return {
                    "model": config["default_model"],
                    "system_prompt": config["default_system_prompt"],
                    "users": {} if server_id else None
                }

    @staticmethod
    async def _save_data(file_path: Path, data: dict):
        """Internal method to save data to file."""
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))

    @staticmethod
    async def save_server_data(server_id: Optional[int], data: dict, user_id: Optional[int] = None):
        """Save server data to JSON file."""
        file_path = ServerDataManager.get_server_file(server_id, user_id)
        lock = await ServerDataManager.get_lock(server_id, user_id)

        async with lock:
            await ServerDataManager._save_data(file_path, data)

    @staticmethod
    async def get_or_create_user(server_id: Optional[int], user_id: int, display_name: str, dm_user_id: Optional[int] = None) -> dict:
        """Get or create user data in server config."""
        data = await ServerDataManager.load_server_data(server_id, dm_user_id)
        now = datetime.now().isoformat()

        if server_id is None:  # DM
            if not data.get("user"):
                data["user"] = {
                    "display_name": display_name,
                    "description": "",
                    "first_seen": now,
                    "last_updated": now
                }
            else:
                data["user"]["display_name"] = display_name
                data["user"]["last_updated"] = now
        else:  # Server
            user_id_str = str(user_id)
            if user_id_str not in data["users"]:
                data["users"][user_id_str] = {
                    "display_name": display_name,
                    "description": "",
                    "first_seen": now,
                    "last_updated": now
                }
            else:
                data["users"][user_id_str]["display_name"] = display_name
                data["users"][user_id_str]["last_updated"] = now

        await ServerDataManager.save_server_data(server_id, data, dm_user_id)
        return data["user"] if server_id is None else data["users"][user_id_str]


async def download_and_encode_image(url: str) -> Optional[dict]:
    """Download an image from URL and return it as a Gemini-compatible part."""
    try:
        response = await httpx_client.get(url, follow_redirects=True)
        if response.status_code != 200:
            logging.error(f"Failed to download image: {response.status_code}")
            return None
        
        content_type = response.headers.get('content-type', '')
        
        # Map content types to Gemini-supported formats
        mime_type_mapping = {
            'image/jpeg': 'image/jpeg',
            'image/jpg': 'image/jpeg',
            'image/png': 'image/png',
            'image/gif': 'image/png',  # Convert GIF to PNG for Gemini
            'image/webp': 'image/webp',
        }
        
        # Get mime type
        mime_type = None
        for ct, mt in mime_type_mapping.items():
            if ct in content_type.lower():
                mime_type = mt
                break
        
        if not mime_type:
            logging.error(f"Unsupported image type: {content_type}")
            return None
        
        # For GIFs, we need to convert to PNG (Gemini doesn't support GIF directly)
        if 'gif' in content_type.lower():
            try:
                from PIL import Image
                import io
                
                img = Image.open(io.BytesIO(response.content))
                # Get first frame
                img = img.convert('RGB')
                
                # Convert to PNG
                output = io.BytesIO()
                img.save(output, format='PNG')
                image_data = output.getvalue()
                mime_type = 'image/png'
            except Exception as e:
                logging.error(f"Failed to convert GIF: {e}")
                return None
        else:
            image_data = response.content
        
        # Return as base64-encoded blob
        return {
            'mime_type': mime_type,
            'data': b64encode(image_data).decode('utf-8')
        }
    
    except Exception as e:
        logging.error(f"Error downloading image from {url}: {e}")
        return None


async def extract_image_urls(text: str, max_urls: int = 3) -> list[str]:
    """Extract image/gif URLs from text."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')
    image_urls = [url for url in urls if any(url.lower().endswith(ext) for ext in image_extensions)]
    
    return image_urls[:max_urls]


def build_system_prompt(base_prompt: str, server_data: dict, server_name: Optional[str], conversation_user_ids: set[int]) -> str:
    """Build enhanced system prompt with user information."""
    now = datetime.now().astimezone()
    prompt = base_prompt.replace("{date}", now.strftime("%B %d %Y")).replace("{time}", now.strftime("%H:%M:%S %Z%z")).strip()
    
    if server_name:
        prompt += f"\n\nCurrent server: {server_name}"
    
    # Add known users info
    users_info = []
    for user_id in conversation_user_ids:
        user_id_str = str(user_id)
        if server_data.get("users") and user_id_str in server_data["users"]:
            user = server_data["users"][user_id_str]
            if user.get("description"):
                users_info.append(f"- <@{user_id}> (Display: {user['display_name']}): {user['description']}")
        elif server_data.get("user") and user.get("description"):  # DM
            users_info.append(f"- {user['display_name']}: {user['description']}")
    
    if users_info:
        prompt += "\n\nKnown users in this conversation:\n" + "\n".join(users_info)
        prompt += "\n\nWhen addressing users, use their display names naturally in conversation."
    
    return prompt


@discord_bot.tree.command(name="model", description="View or switch the current model")
@app_commands.describe(model="Choose a Gemini model")
@app_commands.choices(model=[
    app_commands.Choice(name="Gemini 2.5 Flash", value="gemini-2.5-flash"),
    app_commands.Choice(name="Gemini 2.5 Pro", value="gemini-2.5-pro")
])
async def model_command(interaction: discord.Interaction, model: Optional[str] = None):
    server_id = interaction.guild_id
    user_id = interaction.user.id if server_id is None else None
    
    data = await ServerDataManager.load_server_data(server_id, user_id)
    current_model = data.get("model", config["default_model"])
    
    if model is None:
        await interaction.response.send_message(f"Current model: `{current_model}`")
        return
    
    if model == current_model:
        await interaction.response.send_message(f"Already using: `{current_model}`")
        return
    
    # Check if user is admin
    user_is_admin = interaction.user.id in config["permissions"]["users"]["admin_ids"]
    
    if not user_is_admin:
        await interaction.response.send_message("You don't have permission to change the model.")
        return
    
    data["model"] = model
    await ServerDataManager.save_server_data(server_id, data, user_id)
    
    await interaction.response.send_message(f"Model switched to: `{model}`")
    logging.info(f"Model switched to {model} (server: {server_id or f'DM {user_id}'})")


@discord_bot.tree.command(name="prompt", description="Manage the system prompt")
@app_commands.describe(
    action="Choose an action",
    text="The system prompt text (for 'set' action)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="View current prompt", value="view"),
    app_commands.Choice(name="Set new prompt", value="set"),
    app_commands.Choice(name="Reset to default", value="reset")
])
async def prompt_command(interaction: discord.Interaction, action: str, text: Optional[str] = None):
    server_id = interaction.guild_id
    user_id = interaction.user.id if server_id is None else None
    user_is_admin = interaction.user.id in config["permissions"]["users"]["admin_ids"]
    
    data = await ServerDataManager.load_server_data(server_id, user_id)
    
    if action == "view":
        current_prompt = data.get("system_prompt", config["default_system_prompt"])
        await interaction.response.send_message(f"**Current system prompt:**\n```\n{current_prompt}\n```")
    
    elif action == "set":
        if not user_is_admin:
            await interaction.response.send_message("You don't have permission to change the system prompt.")
            return
        
        if not text:
            await interaction.response.send_message("Please provide the prompt text.")
            return
        
        data["system_prompt"] = text.strip()
        await ServerDataManager.save_server_data(server_id, data, user_id)
        await interaction.response.send_message("System prompt updated successfully!")
    
    elif action == "reset":
        if not user_is_admin:
            await interaction.response.send_message("You don't have permission to reset the system prompt.")
            return
        
        data["system_prompt"] = config["default_system_prompt"]
        await ServerDataManager.save_server_data(server_id, data, user_id)
        await interaction.response.send_message("System prompt reset to default.")


@discord_bot.tree.command(name="known", description="Manage user personalization")
@app_commands.describe(
    action="Choose an action",
    description="Your description (for 'set' action)",
    user="User to manage (admin only)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Set your description", value="set"),
    app_commands.Choice(name="View description", value="view"),
    app_commands.Choice(name="Remove description", value="remove")
])
async def known_command(interaction: discord.Interaction, action: str, description: Optional[str] = None, user: Optional[discord.Member] = None):
    server_id = interaction.guild_id
    dm_user_id = interaction.user.id if server_id is None else None
    user_is_admin = interaction.user.id in config["permissions"]["users"]["admin_ids"]
    
    target_user = user if user else interaction.user
    max_length = config.get("max_user_description_length", 500)
    
    # Check permissions for managing other users
    if user and user.id != interaction.user.id and not user_is_admin:
        await interaction.response.send_message("You don't have permission to manage other users.")
        return
    
    data = await ServerDataManager.load_server_data(server_id, dm_user_id)
    
    if action == "view":
        if server_id is None:  # DM
            user_data = data.get("user", {})
            desc = user_data.get("description", "")
            name = user_data.get("display_name", target_user.display_name)
        else:
            user_id_str = str(target_user.id)
            if user_id_str not in data["users"]:
                await interaction.response.send_message(f"{target_user.mention} hasn't interacted with the bot yet.")
                return
            user_data = data["users"][user_id_str]
            desc = user_data.get("description", "")
            name = user_data.get("display_name", target_user.display_name)
        
        if desc:
            await interaction.response.send_message(f"**{name}'s description:**\n{desc}")
        else:
            await interaction.response.send_message(f"{name} has no description set.")
    
    elif action == "set":
        if not description:
            await interaction.response.send_message("Please provide a description.")
            return
        
        if len(description) > max_length:
            await interaction.response.send_message(f"Description too long! Maximum {max_length} characters.")
            return
        
        # Ensure user exists in data
        await ServerDataManager.get_or_create_user(server_id, target_user.id, target_user.display_name, dm_user_id)
        
        # Reload data after potential creation
        data = await ServerDataManager.load_server_data(server_id, dm_user_id)
        
        if server_id is None:  # DM
            data["user"]["description"] = description.strip()
        else:
            data["users"][str(target_user.id)]["description"] = description.strip()
        
        await ServerDataManager.save_server_data(server_id, data, dm_user_id)
        
        if target_user.id == interaction.user.id:
            await interaction.response.send_message("Your description has been updated!")
        else:
            await interaction.response.send_message(f"Description updated for {target_user.mention}")
    
    elif action == "remove":
        if server_id is None:  # DM
            if data.get("user"):
                data["user"]["description"] = ""
                await ServerDataManager.save_server_data(server_id, data, dm_user_id)
                await interaction.response.send_message("Your description has been removed.")
            else:
                await interaction.response.send_message("No description to remove.")
        else:
            user_id_str = str(target_user.id)
            if user_id_str in data["users"]:
                data["users"][user_id_str]["description"] = ""
                await ServerDataManager.save_server_data(server_id, data, dm_user_id)
                
                if target_user.id == interaction.user.id:
                    await interaction.response.send_message("Your description has been removed.")
                else:
                    await interaction.response.send_message(f"Description removed for {target_user.mention}")
            else:
                await interaction.response.send_message(f"{target_user.mention} hasn't interacted with the bot yet.")


@discord_bot.event
async def on_ready():
    if client_id := config.get("client_id"):
        logging.info(f"\n\nBOT INVITE URL:\nhttps://discord.com/oauth2/authorize?client_id={client_id}&permissions=412317191168&scope=bot\n")
    
    await discord_bot.tree.sync()
    logging.info(f"Bot ready! Logged in as {discord_bot.user}")


@discord_bot.event
async def on_message(new_msg: discord.Message):
    global last_task_time
    
    is_dm = new_msg.channel.type == discord.ChannelType.private
    
    if (not is_dm and discord_bot.user not in new_msg.mentions) or new_msg.author.bot:
        return
    
    # Permission checks
    role_ids = set(role.id for role in getattr(new_msg.author, "roles", ()))
    channel_ids = set(filter(None, (new_msg.channel.id, getattr(new_msg.channel, "parent_id", None), getattr(new_msg.channel, "category_id", None))))
    
    config_data = await asyncio.to_thread(get_config)
    
    allow_dms = config_data.get("allow_dms", True)
    permissions = config_data["permissions"]
    user_is_admin = new_msg.author.id in permissions["users"]["admin_ids"]
    
    (allowed_user_ids, blocked_user_ids), (allowed_role_ids, blocked_role_ids), (allowed_channel_ids, blocked_channel_ids) = (
        (perm["allowed_ids"], perm["blocked_ids"]) for perm in (permissions["users"], permissions["roles"], permissions["channels"])
    )
    
    allow_all_users = not allowed_user_ids if is_dm else not allowed_user_ids and not allowed_role_ids
    is_good_user = user_is_admin or allow_all_users or new_msg.author.id in allowed_user_ids or any(id in allowed_role_ids for id in role_ids)
    is_bad_user = not is_good_user or new_msg.author.id in blocked_user_ids or any(id in blocked_role_ids for id in role_ids)
    
    allow_all_channels = not allowed_channel_ids
    is_good_channel = user_is_admin or allow_dms if is_dm else allow_all_channels or any(id in allowed_channel_ids for id in channel_ids)
    is_bad_channel = not is_good_channel or any(id in blocked_channel_ids for id in channel_ids)
    
    if is_bad_user or is_bad_channel:
        return
    
    # Load server data
    server_id = new_msg.guild.id if new_msg.guild else None
    dm_user_id = new_msg.author.id if server_id is None else None
    server_data = await ServerDataManager.load_server_data(server_id, dm_user_id)
    
    # Get or create user
    await ServerDataManager.get_or_create_user(server_id, new_msg.author.id, new_msg.author.display_name, dm_user_id)
    
    model_name = server_data.get("model", config["default_model"])
    
    max_text = config.get("max_text", 100000)
    max_images = config.get("max_images", 5)
    max_messages = config.get("max_messages", 25)
    max_urls = config.get("max_urls", 3)
    
    # Build message chain
    messages = []
    user_warnings = set()
    curr_msg = new_msg
    conversation_user_ids = set()
    
    while curr_msg is not None and len(messages) < max_messages:
        curr_node = msg_nodes.setdefault(curr_msg.id, MsgNode())
        
        async with curr_node.lock:
            if curr_node.text is None:
                cleaned_content = curr_msg.content.removeprefix(discord_bot.user.mention).lstrip()
                
                # Process attachments
                good_attachments = [att for att in curr_msg.attachments if att.content_type and att.content_type.startswith("image")]
                
                curr_node.text = "\n".join(
                    ([cleaned_content] if cleaned_content else [])
                    + ["\n".join(filter(None, (embed.title, embed.description))) for embed in curr_msg.embeds]
                )
                
                # Download and encode Discord attachments
                curr_node.images = []
                for att in good_attachments[:max_images]:
                    img_part = await download_and_encode_image(att.url)
                    if img_part:
                        curr_node.images.append(img_part)
                
                # Extract and download image URLs from text
                if len(curr_node.images) < max_images:
                    text_image_urls = await extract_image_urls(curr_node.text, max_urls)
                    for img_url in text_image_urls[:max_images - len(curr_node.images)]:
                        img_part = await download_and_encode_image(img_url)
                        if img_part:
                            curr_node.images.append(img_part)
                
                curr_node.role = "model" if curr_msg.author == discord_bot.user else "user"
                curr_node.user_id = curr_msg.author.id if curr_node.role == "user" else None
                curr_node.display_name = curr_msg.author.display_name if curr_node.role == "user" else None
                curr_node.has_bad_attachments = len(curr_msg.attachments) > len(good_attachments)
                
                # Find parent message
                try:
                    if (
                        curr_msg.reference is None
                        and discord_bot.user.mention not in curr_msg.content
                        and (prev_msg_in_channel := ([m async for m in curr_msg.channel.history(before=curr_msg, limit=1)] or [None])[0])
                        and prev_msg_in_channel.type in (discord.MessageType.default, discord.MessageType.reply)
                        and prev_msg_in_channel.author == (discord_bot.user if is_dm else curr_msg.author)
                    ):
                        curr_node.parent_msg = prev_msg_in_channel
                    else:
                        is_public_thread = curr_msg.channel.type == discord.ChannelType.public_thread
                        parent_is_thread_start = is_public_thread and curr_msg.reference is None and curr_msg.channel.parent.type == discord.ChannelType.text
                        
                        if parent_msg_id := curr_msg.channel.id if parent_is_thread_start else getattr(curr_msg.reference, "message_id", None):
                            if parent_is_thread_start:
                                curr_node.parent_msg = curr_msg.channel.starter_message or await curr_msg.channel.parent.fetch_message(parent_msg_id)
                            else:
                                curr_node.parent_msg = curr_msg.reference.cached_message or await curr_msg.channel.fetch_message(parent_msg_id)
                
                except (discord.NotFound, discord.HTTPException):
                    logging.exception("Error fetching parent message")
                    curr_node.fetch_parent_failed = True
            
            # Build content for Gemini
            if curr_node.user_id:
                conversation_user_ids.add(curr_node.user_id)
            
            parts = []
            if curr_node.text[:max_text]:
                # Add user attribution for user messages
                if curr_node.role == "user" and curr_node.display_name:
                    text_content = f"{curr_node.display_name}: {curr_node.text[:max_text]}"
                else:
                    text_content = curr_node.text[:max_text]
                parts.append(text_content)
            
            # Add images (they're already in the correct format)
            parts.extend(curr_node.images[:max_images])
            
            if parts:
                messages.append({"role": curr_node.role, "parts": parts})
            
            # Warnings
            if len(curr_node.text) > max_text:
                user_warnings.add(f"⚠️ Max {max_text:,} characters per message")
            if len(curr_node.images) > max_images:
                user_warnings.add(f"⚠️ Max {max_images} images per message")
            if curr_node.has_bad_attachments:
                user_warnings.add("⚠️ Unsupported attachments")
            if curr_node.fetch_parent_failed or (curr_node.parent_msg is not None and len(messages) == max_messages):
                user_warnings.add(f"⚠️ Only using last {len(messages)} message{'s' if len(messages) != 1 else ''}")
            
            curr_msg = curr_node.parent_msg
    
    logging.info(f"Message received (user: {new_msg.author.display_name}, server: {new_msg.guild.name if new_msg.guild else 'DM'}, conversation length: {len(messages)})")
    
    # Build system prompt
    system_prompt = build_system_prompt(
        server_data.get("system_prompt", config["default_system_prompt"]),
        server_data,
        new_msg.guild.name if new_msg.guild else None,
        conversation_user_ids
    )
    
    # Configure Gemini model
    generation_config = {
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
        safety_settings=safety_settings,
        system_instruction=system_prompt
    )
    
    # Generate response with streaming
    use_plain_responses = config.get("use_plain_responses", False)
    response_msgs = []
    response_contents = []
    
    if not use_plain_responses:
        max_message_length = 4096 - len(" ⚪")
        embed = discord.Embed()
        if user_warnings:
            embed.add_field(name="⚠️ Warnings", value="\n".join(sorted(user_warnings)), inline=False)
    else:
        max_message_length = 2000
    
    async def reply_helper(**reply_kwargs):
        reply_target = new_msg if not response_msgs else response_msgs[-1]
        response_msg = await reply_target.reply(**reply_kwargs)
        response_msgs.append(response_msg)
        
        msg_nodes[response_msg.id] = MsgNode(parent_msg=new_msg)
        await msg_nodes[response_msg.id].lock.acquire()
    
    try:
        async with new_msg.channel.typing():
            # Start generation
            response = await asyncio.to_thread(
                model.generate_content,
                messages[::-1],
                stream=True
            )
            
            curr_content = ""
            chunk_buffer = ""
            last_edit_time = 0
            
            for chunk in response:
                try:
                    if hasattr(chunk, 'text'):
                        chunk_buffer += chunk.text
                        curr_content += chunk.text
                        
                        current_time = datetime.now().timestamp()
                        time_since_edit = current_time - last_edit_time
                        
                        # Check if we need to start a new message
                        if response_contents and len(response_contents[-1] + chunk_buffer) > max_message_length:
                            # Finalize current message
                            if not use_plain_responses:
                                embed.description = response_contents[-1]
                                embed.color = discord.Color.dark_green()
                                await response_msgs[-1].edit(embed=embed)
                            
                            # Start new message with accumulated buffer
                            response_contents.append(chunk_buffer)
                            chunk_buffer = ""
                            
                            if not use_plain_responses:
                                embed = discord.Embed()  # Fresh embed for new message
                                embed.description = response_contents[-1] + " ⚪"
                                embed.color = discord.Color.orange()
                                await reply_helper(embed=embed, silent=True)
                                last_edit_time = current_time
                            
                            continue
                        
                        # Initialize first message
                        if response_contents == []:
                            response_contents.append(chunk_buffer)
                            chunk_buffer = ""
                            
                            if not use_plain_responses:
                                embed.description = response_contents[-1] + " ⚪"
                                embed.color = discord.Color.orange()
                                await reply_helper(embed=embed, silent=True)
                                last_edit_time = current_time
                            
                            continue
                        
                        # Update message periodically
                        if not use_plain_responses and time_since_edit >= EDIT_DELAY_SECONDS:
                            embed.description = response_contents[-1] + chunk_buffer + " ⚪"
                            embed.color = discord.Color.orange()
                            await response_msgs[-1].edit(embed=embed)
                            last_edit_time = current_time
                
                except Exception as e:
                    logging.error(f"Error processing chunk: {e}")
                    continue
            
            # Final update
            if not use_plain_responses:
                if chunk_buffer:
                    response_contents[-1] += chunk_buffer
                
                for i, content in enumerate(response_contents):
                    embed.description = content
                    embed.color = discord.Color.dark_green()
                    
                    if i < len(response_msgs):
                        await response_msgs[i].edit(embed=embed)
                    else:
                        await reply_helper(embed=embed, silent=True)
            else:
                if chunk_buffer:
                    response_contents[-1] += chunk_buffer
                
                for content in response_contents:
                    if len(response_msgs) == 0 or response_msgs[-1].content:
                        await reply_helper(content=content)
                    else:
                        await response_msgs[-1].edit(content=content)
    
    except Exception as e:
        logging.exception("Error generating response")
        error_msg = "Sorry, I encountered an error while generating a response."
        
        if not use_plain_responses:
            embed.description = error_msg
            embed.color = discord.Color.red()
            if response_msgs:
                await response_msgs[-1].edit(embed=embed)
            else:
                await reply_helper(embed=embed)
        else:
            if response_msgs:
                await response_msgs[-1].edit(content=error_msg)
            else:
                await reply_helper(content=error_msg)
    
    # Store final response
    for response_msg in response_msgs:
        msg_nodes[response_msg.id].text = "".join(response_contents)
        msg_nodes[response_msg.id].lock.release()
    
    # Clean up old message nodes
    if (num_nodes := len(msg_nodes)) > MAX_MESSAGE_NODES:
        for msg_id in sorted(msg_nodes.keys())[: num_nodes - MAX_MESSAGE_NODES]:
            async with msg_nodes.setdefault(msg_id, MsgNode()).lock:
                msg_nodes.pop(msg_id, None)


async def main():
    await discord_bot.start(config["bot_token"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")