# How to Find Morpho Market ID

## What is a Market ID?

A **Market ID** is a unique identifier (bytes32 hash) for each Morpho market. Each market represents a specific lending pair, like:
- WBTC/USDC market
- WETH/USDC market
- etc.

## How to Find Market ID

### Method 1: From Morpho App URL (Easiest!)

When you visit a market on Morpho's app, the URL contains the market ID:

**Example URL:**
```
https://app.morpho.org/monad/market/0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d/weth-usdc?subTab=yourPosition
```

**The Market ID is the long hex string after `/market/`:**
```
0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d
```

**Format:**
- Starts with `0x`
- 64 hex characters (32 bytes)
- Total length: 66 characters

### Method 2: From Your URLs

From your URLs:

**WBTC/USDC Market:**
```
URL: https://app.morpho.org/monad/market/0xe35c5abc6418b6319b014e07aa3c86163a870a957284128f03cf7a9e414f8899/wbtc-usdc?subTab=yourPosition

Market ID: 0xe35c5abc6418b6319b014e07aa3c86163a870a957284128f03cf7a9e414f8899
```

**WETH/USDC Market:**
```
URL: https://app.morpho.org/monad/market/0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d/weth-usdc?subTab=yourPosition

Market ID: 0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d
```

### Method 3: Using GraphQL API

The bot can automatically find market IDs using Morpho's GraphQL API. If you just add an address without market ID:

```
/add morpho 1.5 0xYourAddress
```

The bot will try to:
1. Query Morpho's GraphQL API for your positions
2. Automatically find all markets you're in
3. Check health factors for all of them

### Method 4: From Morpho App Interface

1. Go to https://app.morpho.org/monad
2. Connect your wallet
3. Navigate to your position
4. The market ID is shown in:
   - The URL (as shown above)
   - Or in the position details panel

## Using Market IDs in the Bot

### Option 1: Let Bot Find Automatically (Recommended)
```
/add morpho 1.5 0xYourAddress
```
Bot will query API to find your markets automatically.

### Option 2: Specify Market ID Manually
```
/add morpho 1.5 0xYourAddress 0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d
```
Use this if:
- You want to monitor a specific market
- API doesn't find your markets automatically
- You want faster checks (skips API call)

### Option 3: Monitor Multiple Markets

You can add the same address multiple times with different market IDs:

```
/add morpho 1.5 0xYourAddress 0xe35c5abc6418b6319b014e07aa3c86163a870a957284128f03cf7a9e414f8899
/add morpho 1.5 0xYourAddress 0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d
```

This monitors both your WBTC/USDC and WETH/USDC positions separately.

## Your Market IDs

Based on your URLs:

1. **WBTC/USDC Market:**
   - Market ID: `0xe35c5abc6418b6319b014e07aa3c86163a870a957284128f03cf7a9e414f8899`

2. **WETH/USDC Market:**
   - Market ID: `0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d`

## Quick Test

Try adding with market ID:
```
/add morpho 1.5 0x12959F938A6ab2D0F10e992470b6e19807a95477 0x409f2824aee2d8391d4a5924935e13312e157055e262b923b60c9dcb47e6311d
```

Or let the bot find it automatically:
```
/add morpho 1.5 0x12959F938A6ab2D0F10e992470b6e19807a95477
```

