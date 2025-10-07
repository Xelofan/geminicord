# Troubleshooting Guide

Common issues and their solutions.

## Bot Not Responding

### Issue: Bot doesn't reply when mentioned
**Possible causes:**
1. MESSAGE CONTENT INTENT not enabled
2. Bot lacks permissions in the channel
3. User/channel is blocked in config

**Solutions:**
1. Go to Discord Developer Portal → Your App → Bot → Enable "MESSAGE CONTENT INTENT"
2. Check bot role permissions: "Read Messages", "Send Messages", "Embed Links"
3. Review `permissions` section in config.yaml:
   ```yaml
   permissions:
     users:
       blocked_ids: []  # Make sure your ID isn't here
     channels:
       blocked_ids: []  # Make sure channel ID isn't here
   ```

### Issue: Bot responds in some channels but not others
**Possible causes:**
1. Channel-specific permissions
2. Channel in blocked list

**Solutions:**
1. Check if the bot has permissions in that specific channel
2. Review channel permissions in config.yaml:
   ```yaml
   permissions:
     channels:
       allowed_ids: []  # Empty means all allowed
       blocked_ids: []  # Check this list
   ```

## Configuration Issues

### Issue: "FileNotFoundError: config.yaml"
**Solution:**
```bash
cp config-example.yaml config.yaml
# Then edit config.yaml with your tokens
```

### Issue: Bot starts but crashes immediately
**Possible causes:**
1. Invalid bot token
2. Invalid API key
3. Missing required config fields

**Solutions:**
1. Double-check your Discord bot token (no spaces, complete token)
2. Verify Google AI API key at https://aistudio.google.com/app/apikey
3. Ensure config.yaml has all required fields:
   ```yaml
   bot_token: "required"
   gemini_api_key: "required"
   ```

### Issue: "Error loading server data"
**Possible causes:**
1. Corrupted JSON file
2. Permission issues with server_data directory

**Solutions:**
1. Delete the problematic JSON file (it will be recreated)
2. Check directory permissions:
   ```bash
   chmod 755 server_data/
   ```

## Command Issues

### Issue: "/model command not working"
**Possible causes:**
1. User is not an admin
2. Commands not synced

**Solutions:**
1. Add your user ID to admin_ids in config.yaml:
   ```yaml
   permissions:
     users:
       admin_ids: [YOUR_USER_ID_HERE]
   ```
2. Wait a few minutes for Discord to sync commands, or restart bot

### Issue: "Unknown command" error
**Solution:**
Commands need time to sync. Wait 5-10 minutes after starting the bot, or kick and re-invite the bot to force sync.

### Issue: "/known command shows error"
**Possible causes:**
1. Description too long
2. JSON file corruption

**Solutions:**
1. Keep descriptions under 500 characters (configurable in config.yaml)
2. Check console logs for specific error messages

## Streaming Issues

### Issue: Response stops mid-sentence
**Possible causes:**
1. Network interruption
2. API timeout
3. Rate limiting

**Solutions:**
1. Check your internet connection
2. Try again - the bot has retry logic built in
3. If persistent, try setting `use_plain_responses: true` in config

### Issue: Responses are very slow
**Possible causes:**
1. Using a more complex model
2. Large conversation history
3. Google Search grounding enabled

**Solutions:**
1. Switch to `gemini-2.0-flash-exp` for faster responses
2. Reduce `max_messages` in config.yaml
3. Set `enable_search_grounding: false` if you don't need search

### Issue: Multiple partial messages instead of one response
**Expected behavior:**
This is normal! Long responses are automatically split to stay within Discord's message length limits.

## API Issues

### Issue: "API key not valid"
**Solutions:**
1. Verify your API key at https://aistudio.google.com/app/apikey
2. Make sure you copied the entire key (they're long!)
3. Ensure no extra spaces in config.yaml
4. Try generating a new API key

### Issue: "Quota exceeded" or "Resource exhausted"
**Solutions:**
1. Check your Google AI Studio quota/limits
2. Wait for quota to reset (usually daily)
3. Consider upgrading your API plan if needed

### Issue: "Model not found" error
**Solution:**
Make sure you're using one of the supported models:
- `gemini-2.0-flash-exp`
- `gemini-exp-1206`

Note: Model names may change as Google updates their API. Check Google AI Studio for current models.

## Image Processing Issues

### Issue: Bot doesn't process uploaded images
**Possible causes:**
1. Model doesn't support vision
2. max_images set to 0

**Solutions:**
1. Use a vision-capable model (both supported models have vision)
2. Check config.yaml:
   ```yaml
   max_images: 5  # Should be > 0
   ```

### Issue: External image URLs not working
**Possible causes:**
1. URL not directly pointing to an image
2. URL blocked by firewall/privacy settings
3. Image format not supported

**Solutions:**
1. Make sure URL ends in .jpg, .png, .gif, etc.
2. Try uploading the image directly to Discord instead
3. Supported formats: JPG, PNG, GIF, WebP, BMP

## Permission Issues

### Issue: "You don't have permission to change the model"
**Solution:**
Add your Discord user ID to the admin list:
```yaml
permissions:
  users:
    admin_ids: [YOUR_USER_ID_HERE]
```

To get your user ID:
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click your name → Copy User ID

### Issue: Bot works in DMs but not in servers
**Possible causes:**
1. allow_dms enabled but server permissions restricted
2. Bot role positioning

**Solutions:**
1. Check permissions config allows server usage
2. Ensure bot role is high enough in server role hierarchy

## Docker Issues

### Issue: "Cannot connect to Docker daemon"
**Solutions:**
1. Make sure Docker is running: `docker ps`
2. On Linux: `sudo systemctl start docker`
3. On Mac/Windows: Start Docker Desktop

### Issue: Bot container keeps restarting
**Possible causes:**
1. Configuration error
2. Missing files

**Solutions:**
1. Check logs: `docker compose logs -f`
2. Ensure config.yaml exists and is valid
3. Verify all files are present

### Issue: "Permission denied" when accessing files
**Solution:**
```bash
# Fix permissions on Linux
sudo chown -R $USER:$USER server_data/
chmod 755 server_data/
```

## Data/Storage Issues

### Issue: User descriptions not saving
**Possible causes:**
1. File system permissions
2. server_data directory doesn't exist

**Solutions:**
1. Create the directory: `mkdir server_data`
2. Check permissions: `chmod 755 server_data`

### Issue: Bot forgets settings after restart
**Possible causes:**
1. JSON files not being written
2. Using read-only volume in Docker

**Solutions:**
1. Check Docker volume configuration in docker-compose.yaml
2. Make sure server_data is writable:
   ```yaml
   volumes:
     - ./server_data:/app/server_data  # No :ro here!
   ```

## Performance Issues

### Issue: Bot uses too much memory
**Possible causes:**
1. Large message cache
2. Many servers with active conversations

**Solutions:**
1. Reduce `max_messages` in config
2. The bot automatically cleans old cache (MAX_MESSAGE_NODES = 500)
3. Restart bot periodically if needed

### Issue: High CPU usage
**Possible causes:**
1. Streaming many messages simultaneously
2. Processing large images

**Solutions:**
1. This is normal during active conversations
2. CPU usage drops when idle
3. Use `use_plain_responses: true` for lower CPU usage

## Getting Help

If none of these solutions work:

1. **Check the logs** - They contain detailed error information:
   ```bash
   # Docker:
   docker compose logs -f
   
   # Python:
   # Check terminal output
   ```

2. **Enable debug logging** - Add to the top of bot.py:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Test with minimal config** - Try with default settings and gradually add customizations

4. **Verify API status**:
   - Discord: https://discordstatus.com
   - Google AI: https://status.cloud.google.com

5. **Check versions**:
   ```bash
   pip list | grep discord
   pip list | grep google-generativeai
   ```

6. **Create an issue** - If you still have problems, open an issue with:
   - Error messages from logs
   - Your config.yaml (with tokens removed!)
   - Steps to reproduce the issue
   - Bot version and Python version

## Prevention Tips

1. **Regular backups**: Back up your `server_data/` directory
2. **Monitor logs**: Check logs periodically for warnings
3. **Keep updated**: Update dependencies regularly
4. **Test changes**: Test configuration changes in a test server first
5. **Document customizations**: Keep notes on what you've changed

## Still Having Issues?

- Review the [README.md](README.md) for feature documentation
- Check the [QUICKSTART.md](QUICKSTART.md) for setup steps
- Join the Discord server (if available) for community support
- Open a GitHub issue with detailed information