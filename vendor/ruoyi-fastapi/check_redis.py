# -*- coding: utf-8 -*-
"""Redis 连接自检脚本：读取 .env.dev 配置并尝试连接 Redis，供 start.bat 启动前调用。

返回码：0 连接成功；1 连接失败（认证错误 / 网络不通 / 配置缺失）。
"""
import os
import sys

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.dev")


def read_env_value(key: str) -> str | None:
    """从 .env.dev 读取指定键的值（支持 'KEY = value' 与 'KEY=value' 两种格式）。"""
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + " =") or line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip("'").strip('"')
    except OSError:
        pass
    return None


def main() -> int:
    host = read_env_value("REDIS_HOST") or "127.0.0.1"
    try:
        port = int(read_env_value("REDIS_PORT") or 6379)
        db = int(read_env_value("REDIS_DATABASE") or 0)
    except ValueError:
        print("[错误] .env.dev 中 REDIS_PORT / REDIS_DATABASE 不是合法数字")
        return 1
    password = read_env_value("REDIS_PASSWORD") or None

    try:
        import redis

        client = redis.Redis(host=host, port=port, password=password, db=db, socket_timeout=5)
        client.ping()
        print("[OK] Redis 连接成功（{}:{} db={}）".format(host, port, db))
        return 0
    except redis.exceptions.AuthenticationError:
        print("[错误] Redis 需要密码认证：请在 .env.dev 中配置 REDIS_PASSWORD 后重新运行")
        return 1
    except Exception as e:  # noqa: BLE001
        print("[错误] Redis 连接失败（{}:{}）：{}".format(host, port, e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
