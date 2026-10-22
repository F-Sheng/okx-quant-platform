"""
API 连接测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def test_api_connection():
    """测试 API 连接"""
    print("\n" + "=" * 60)
    print("OKX API 连接测试")
    print("=" * 60 + "\n")

    from config.okx_config import config
    from execution.okx_client import OKXClient

    client = OKXClient(
        api_key=config.exchange_config['api_key'],
        secret_key=config.exchange_config['secret_key'],
        passphrase=config.exchange_config['passphrase'],
        trading_mode='demo'
    )

    tests = [
        ("获取账户余额", lambda: client.get_usd_balance()),
        ("获取 BTC 价格", lambda: client.get_ticker_price('BTC-USDT')),
        ("获取资金费率", lambda: client.get_funding_rate('BTC-USDT-SWAP')),
    ]

    results = []

    for name, test_func in tests:
        print(f"\n测试: {name}")
        print("-" * 60)

        start_time = time.time()
        try:
            result = test_func()
            elapsed = time.time() - start_time

            if result is not None and result != 0 and result != {}:
                print(f"[OK] 成功 ({elapsed:.2f}s)")
                print(f"     结果: {result}")
                results.append((name, True, elapsed))
            else:
                print(f"[FAIL] 返回空 ({elapsed:.2f}s)")
                results.append((name, False, elapsed))

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] 异常 ({elapsed:.2f}s): {e}")
            results.append((name, False, elapsed))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    success_count = sum(1 for _, success, _ in results if success)
    total_count = len(results)

    print(f"\n成功: {success_count}/{total_count}")
    print(f"\n详细结果:")
    for name, success, elapsed in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}: {elapsed:.2f}s")

    if success_count == 0:
        print("\n[警告] 所有 API 调用都失败了!")
        print("可能的原因:")
        print("  1. 网络无法连接到 OKX (可能需要 VPN/代理)")
        print("  2. API 密钥无效或已过期")
        print("  3. OKX 服务器维护中")
        print("\n建议:")
        print("  - 检查网络连接")
        print("  - 尝试使用 VPN")
        print("  - 验证 API 密钥是否正确")

    print()


if __name__ == '__main__':
    test_api_connection()
