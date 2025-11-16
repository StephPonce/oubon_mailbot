# 🔧 BLANK PAGE FIX - STEP BY STEP

## The Problem
Your frontend loads but shows blank page. This is likely caused by:
1. **React type mismatch** (React 18 runtime but React 19 types)
2. **Cached broken build**
3. **Missing lucide-react**

---

## ✅ SOLUTION - Run These Commands

### Step 1: Run Diagnostic
```bash
cd '/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot/frontend'
chmod +x DIAGNOSE.sh
./DIAGNOSE.sh
```

This will tell you EXACTLY what's wrong.

---

### Step 2: Apply Fix
```bash
chmod +x FIX_BLANK_PAGE.sh
./FIX_BLANK_PAGE.sh
```

This will:
- Fix React type mismatch
- Reinstall lucide-react
- Clear build caches
- Start dev server

---

### Step 3: Test Minimal React
If fix script doesn't work, test if React itself works:

```bash
# Backup current App.tsx
cp src/App.tsx src/App.FULL.tsx

# Use minimal test version
cp src/App.MINIMAL_TEST.tsx src/App.tsx

# Restart dev server
npm run dev
```

Open http://localhost:5173

**If you see "✅ REACT IS WORKING!":**
- React is fine, issue is in your components
- Restore full app: `cp src/App.FULL.tsx src/App.tsx`
- Check browser console for errors

**If still blank:**
- It's a build/config issue
- Run: `npm install`
- Delete node_modules and reinstall

---

## 🔍 Common Issues & Fixes

### Issue 1: "Cannot find module 'lucide-react'"
```bash
npm install lucide-react@0.552.0
```

### Issue 2: React type errors
```bash
npm install --save-dev @types/react@18.3.1 @types/react-dom@18.3.1
```

### Issue 3: Port 5173 already in use
```bash
pkill -f vite
npm run dev
```

### Issue 4: Backend not responding
```bash
# In another terminal
cd '/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot'
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

---

## 📋 Checklist

After running fixes:

- [ ] Dev server starts without errors
- [ ] Browser shows http://localhost:5173
- [ ] Hard refresh (Cmd+Shift+R)
- [ ] Check browser console (F12) for errors
- [ ] Backend running on port 8001
- [ ] Network tab shows API calls

---

## 🆘 If Nothing Works

1. **Nuclear option:**
   ```bash
   cd '/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot/frontend'
   rm -rf node_modules package-lock.json
   npm install
   npm run dev
   ```

2. **Screenshot these:**
   - Browser console (F12 → Console)
   - Network tab (F12 → Network)
   - Terminal output from `npm run dev`

3. **Share with Claude** for deeper diagnosis

---

## ✅ Success Indicators

You'll know it's fixed when you see:

1. **Terminal:** 
   ```
   VITE v5.x.x ready in XXXms
   ➜ Local: http://localhost:5173/
   ```

2. **Browser:** 
   - Green banner: "✅ V2 INTELLIGENCE PLATFORM"
   - Dark sidebar on left
   - Stats cards
   - Product grid

3. **Console:** 
   - No red errors
   - API calls returning 200 OK

---

**Still stuck? Run DIAGNOSE.sh and share the output!**
