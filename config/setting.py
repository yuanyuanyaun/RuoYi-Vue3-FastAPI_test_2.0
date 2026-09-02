"""
setting：全局配置模块。

职责：
    集中管理被测系统（RuoYi-Vue3-FastAPI）的全部环境相关配置项，
    供 utils/api_client.py（HTTP 请求层）与 utils/mysql_helper.py（数据库访问层）导入使用。

配置项说明：
    BASE_URL    被测后端服务地址，作为 HTTP 请求的统一前缀
                （默认本机：http://127.0.0.1:9099/，对应 vendor/ruoyi-fastapi 一键启动的本地后端,如有需要可在下方自行更改）
    TIMEOUT     请求超时秒数，兜底注入每次 HTTP 请求，避免请求无界挂起
    LOG_LEVEL   日志级别，决定请求/响应日志的输出粒度
    DB_HOST     数据库主机地址（默认本机：127.0.0.1，与内置被测系统的 .env.dev 保持一致）
    DB_PORT     数据库端口（默认 3306）
    DB_USER     数据库用户名（默认 root）
    DB_PASSWORD 数据库密码（默认 123456）
    DB_NAME     数据库名（默认 ruoyi-fastapi）

环境移植策略：
    所有配置项均支持环境变量覆盖，便于 CI 流水线与多环境切换，无需修改代码：
        set BASE_URL=http://自己的后端地址
        set DB_HOST=自己的数据库地址
    随后直接运行 pytest 即可完成环境移植。
"""
import os

BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:9099/')
TIMEOUT = int(os.getenv('TIMEOUT', 10))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "ruoyi-fastapi")

# 独立运行自检：仅开发调试时以 python config/setting.py 直接运行，
# pytest 采集阶段不会执行该块；块内 a[-3:] 为历史遗留的调试代码，保留原样
if __name__ == "__main__":
    print('OK')


