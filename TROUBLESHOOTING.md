# 🚨 Dependency Installation & Troubleshooting Guide

## Issues Fixed:

### 1. Python Dependencies (Relayer)
**Error:** `ModuleNotFoundError: No module named 'genlayer'`

**Solution:**
```bash
pip install -r requirements.txt
# OR manually:
pip install genlayer web3 python-dotenv
```

### 2. Frontend Dependencies
**Errors:**
- `Can't resolve '@radix-ui/react-tabs'`
- `Can't resolve 'ethers'`
- `Can't resolve './wallet'` (fixed import path)

**Solution:**
```bash
cd frontend
npm install
```

### 3. Import Path Fix
**Fixed:** `useOracle.ts` import path corrected from `./wallet` to `@/lib/genlayer/wallet`

## 🔧 Quick Fix Script

Run this script to install all dependencies:

```bash
chmod +x install_deps.sh
./install_deps.sh
```

## 🧪 Testing After Installation

### 1. Start Frontend:
```bash
cd frontend
npm run dev
```

### 2. Start Relayer:
```bash
cd relayer
python relayer_keeper.py
```

### 3. Test Full System:
1. Open http://localhost:3000
2. Connect MetaMask to Polygon Amoy
3. Register chain using Oracle Manager
4. Create a test market
5. Place bets
6. Wait for AI resolution
7. Claim winnings

## 📋 Manual Installation (if script fails):

### Python Dependencies:
```bash
pip install genlayer==0.1.1
pip install web3==6.15.1
pip install python-dotenv==1.0.1
```

### Frontend Dependencies:
```bash
cd frontend
npm install @radix-ui/react-tabs@^1.1.0
npm install ethers@^6.13.4
```

## 🔍 Verification:

### Check Python:
```bash
python -c "import genlayer; print('✅ genlayer OK')"
python -c "import web3; print('✅ web3 OK')"
```

### Check Frontend:
```bash
cd frontend
npm list genlayer-js
npm list ethers
npm list @radix-ui/react-tabs
```

## 🚨 Common Issues:

1. **Python Path Issues**: Use `python3` instead of `python`
2. **Permission Errors**: Use `pip install --user` or `sudo pip install`
3. **Node Version**: Ensure Node.js >= 18
4. **Cache Issues**: Clear npm cache with `npm cache clean --force`

## 🎯 Expected Results:

After successful installation:
- ✅ Frontend compiles without errors
- ✅ Relayer starts without import errors
- ✅ Full prediction market system functional
- ✅ AI resolution and automatic payouts working

---

**Run the installation script and restart both services!** 🚀