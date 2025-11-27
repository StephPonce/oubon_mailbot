# Safari Troubleshooting Guide

## Current Status
✅ Backend running at: http://localhost:8001
✅ Frontend running at: http://localhost:5173
✅ API responding correctly

## How to Access in Safari

1. **Open Safari** and navigate to:
   ```
   http://localhost:5173
   ```

2. **Alternative URL** (if localhost doesn't work):
   ```
   http://127.0.0.1:5173
   ```

## Safari-Specific Issues & Fixes

### Issue 1: Blank Page or "Can't Connect to Server"

**Symptoms:**
- Safari shows blank white page
- Browser console shows connection errors
- Network tab shows failed requests

**Solutions:**
1. **Clear Safari Cache:**
   - Safari > Clear History...
   - Select "all history"
   - Click "Clear History"

2. **Disable Cross-Site Tracking Prevention:**
   - Safari > Preferences > Privacy
   - Uncheck "Prevent cross-site tracking"
   - Refresh the page

3. **Check Developer Console:**
   - Press `Cmd + Option + I` to open Developer Tools
   - Go to Console tab
   - Look for red error messages
   - Common errors:
     - `CORS policy` - Backend CORS issue (already configured)
     - `Mixed Content` - HTTP/HTTPS mismatch (not applicable here)
     - `Failed to fetch` - Backend not running or wrong URL

### Issue 2: API Requests Failing

**Symptoms:**
- Dashboard loads but shows no data
- Console shows 404 or network errors

**Solutions:**
1. **Verify Backend is Running:**
   ```bash
   curl http://localhost:8001/health
   ```
   Should return: `{"status":"ok",...}`

2. **Check Network Tab in Safari:**
   - Open Developer Tools (Cmd+Option+I)
   - Go to Network tab
   - Refresh page
   - Look for failed requests (red)
   - Click on failed request to see details

### Issue 3: Localhost Resolution

**Symptoms:**
- "Server not found" error
- DNS resolution failures

**Solutions:**
1. **Use 127.0.0.1 instead:**
   - Try: http://127.0.0.1:5173

2. **Check /etc/hosts:**
   ```bash
   cat /etc/hosts | grep localhost
   ```
   Should have: `127.0.0.1 localhost`

### Issue 4: Cookies/Storage Issues

**Symptoms:**
- Settings not saving
- Session data lost on refresh

**Solutions:**
1. **Allow Local Storage:**
   - Safari > Preferences > Privacy
   - Ensure "Block all cookies" is NOT checked

2. **Clear Website Data:**
   - Safari > Preferences > Privacy
   - Click "Manage Website Data"
   - Remove localhost:5173
   - Try again

## Quick Diagnostic Commands

Run these in Terminal to verify everything is working:

```bash
# Check if backend is responding
curl http://localhost:8001/health

# Check if frontend is serving
curl http://localhost:5173

# Test a specific API endpoint
curl http://localhost:8001/api/portfolio/overview

# Check what's listening on the ports
lsof -i :5173 -i :8001 | grep LISTEN
```

## Still Having Issues?

1. **Try a Different Browser** (Chrome/Firefox) to isolate Safari-specific issues
2. **Check Backend Logs:**
   ```bash
   tail -f /tmp/backend.log
   ```
3. **Check Frontend Console** for specific error messages
4. **Restart Services:**
   ```bash
   # Kill existing processes
   pkill -f uvicorn
   pkill -f vite

   # Restart using the startup script
   ./scripts/START_SERVERS.sh
   ```

## What to Report

If you need help, provide:
1. Exact error message from Safari Console
2. Screenshot of Network tab showing failed requests
3. Output from `curl http://localhost:8001/health`
4. Safari version: Safari > About Safari
