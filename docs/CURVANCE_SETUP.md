# Curvance Protocol Integration

## Required Contract Address

To use Curvance health checking, you need the **ProtocolReader** contract address on Monad.

## Current Addresses Available

From Curvance's deployment info:
- `SimpleZapper`: `0x5af9b7cAc0530d3C9e11C23B7A69Cce335B8C395`
- `NativeVaultZapper`: `0x1D60A3F3f84F095b3D6001fbc135F6D42c812269`
- `OracleManager`: `0x32fad39e79fac67f80d1c86cbd1598043e52cdb6`
- `RedstoneClassicAdaptor`: `0x0fa602b3e748438a3f1599206ed6dc497ab3331e`
- `CentralRegistry`: `0x1310f352f1389969ece6741671c4b919523912ff`

## Questions to Ask Curvance Team

1. **What is the ProtocolReader contract address on Monad (Chain ID 143)?**
   - This is the contract we need to call `getAllDynamicState()` for health factor checking.

2. **Can we query the ProtocolReader address from CentralRegistry?**
   - Some protocols store reader/viewer addresses in their registry contracts.

3. **Is there an alternative way to query user health factors?**
   - If ProtocolReader isn't deployed, is there another contract or API we can use?

## Setup

Once you have the ProtocolReader address, add it to your `.env` file:

```bash
CURVANCE_PROTOCOL_READER_ADDRESS=0x... (actual address)
```

## Testing

After setting the address, test with:
```bash
/add curvance 1.5 0xYourAddress
/check
```

