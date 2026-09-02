"""用户模块-新增用户 测试用例。

覆盖接口：
    POST /system/user   添加用户接口：全字段创建用户并建立角色/岗位关联

测试策略：
    数据驱动：data/user/user_creat_data.json 提供 success_cases / fail_code_cases /
    fail_status_cases / defect_cases 四类场景数据，每条用例数据为完整创建 payload。
    正向 / 反向 / 边界 / 已知缺陷(xfail) 场景全覆盖：
    - 正向场景：HTTP 200 + 业务 code 200 + success=True；
    - 业务失败：HTTP 200 但业务 code 601（校验拦截）/ 500（唯一性冲突）；
    - HTTP 失败：4xx/5xx 由 requests 抛 HTTPError，断言响应状态码；
    - 已知缺陷(xfail)：期望正常拦截，实际 500 泄漏或假成功；
    - 唯一性：userName 为登录账号唯一键，其他字段相同不影响重复添加；
    - 边界值：备注恰好 500 字符成功（DB varchar(500) 上限），501 字符触发缺陷。
    代表覆盖：邮箱/手机号的格式、长度、唯一性校验仅在本模块验证，其他模块同字段不重复测试。
    清理策略：数据驱动场景统一复用 creat_user 夹具，创建成功后由夹具自动级联清理。
"""

import json
import pytest
import allure
import time
import requests

# 模块导入时一次性加载数据驱动数据，避免每个用例重复读文件；数据按场景类型分组
with open("data/user/user_creat_data.json", encoding="utf-8") as f:
    data = json.load(f)


# 历史清理工具函数：早期用例手动按用户名查询并删除测试数据；
# 新用例统一使用 creat_user 夹具自动级联清理，此函数保留供参考与复用
def cleanup_user(user_api, user_name):
    """按用户名查询并删除测试用户：历史清理方式，新用例统一改用 creat_user 夹具自动级联清理。"""
    query = user_api.list(userName=user_name).json()
    if query.get("total") == 1:
        user_api.delete(query["rows"][0]["userId"])


@pytest.mark.user
@allure.feature("用户模块")
@allure.story("添加用户接口")
class TestUserCreat:
    """新增用户接口用例：按成功/业务失败/HTTP 失败/唯一性/缺陷/备注边界分组，数据驱动场景复用 creat_user 夹具自动清理。"""

    @pytest.mark.parametrize("case", data["success_cases"])
    @allure.title("{case[name]}")
    def test_creat_success(self, creat_user, case):
        """正向场景：数据驱动完整 payload 创建用户成功，断言 HTTP 200 + 业务 code 200 + success=True。"""
        # creat_user 夹具按 payload 完成创建，创建成功后由夹具自动级联清理
        resp, _, _ = creat_user(**case["payload"])
        assert resp.status_code == 200
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] == True

    @pytest.mark.parametrize("case", data["fail_code_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_code(self, creat_user, case):
        """业务失败场景：请求被业务层拦截（HTTP 仍为 200），断言业务返回码 601（校验拦截）/ 500（唯一性冲突）。"""
        # 业务失败场景：HTTP 状态码仍为 200，业务 code 由后端业务规则决定，按数据文件期望值断言
        resp, _, _ = creat_user(**case["payload"])
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] == False

    @pytest.mark.parametrize("case", data["fail_status_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_status(self, creat_user, case):
        """HTTP 失败场景：请求触发 4xx/5xx，requests 抛出 HTTPError，断言响应 HTTP 状态码。"""
        # 4xx/5xx 由 requests 库包装为 HTTPError，捕获后断言响应状态码与数据文件期望一致
        with pytest.raises(requests.exceptions.HTTPError) as e:
            creat_user(**case["payload"])
        assert e.value.response.status_code == case["expected_status"]

    @allure.title("除userName,外其他字段相同可重复添加")
    def test_creat_user_repeat_other_fields(self, creat_user):
        """唯一性验证：userName 为登录账号唯一键，其他字段（昵称/部门/密码等）完全相同也可重复添加。"""
        # 以同一时间戳构造仅 userName 不同的两个 payload（dup_a/dup_b），保证数据唯一且可区分
        ts = time.strftime('%Y%m%d%H%M%S')
        name_a = f"dup_a_{ts}"
        name_b = f"dup_b_{ts}"
        common = {
            "nickName": "同名昵称",
            "password": "Test@123456",
            "deptId": 100,
            "sex": "0",
            "status": "0",
            "remark": "相同备注"
        }
        # 两个用户除 userName 外全部字段相同均创建成功，即证明唯一性只约束 userName
        r1, _, _ = creat_user(**common, **{"userName": name_a})
        assert r1.json()["code"] == 200
        r2, _, _ = creat_user(**common, **{"userName": name_b})
        assert r2.json()["code"] == 200

    # 缺陷场景数据：逐条套用 xfail 标记（期望正常拦截，实际 500 泄漏或假成功），
    # 已知缺陷由 reason 记录缺陷描述与前端约束背景
    defect_params = [
        pytest.param(
            use_data,
            marks=pytest.mark.xfail(
                reason=f"已知缺陷：{use_data['defect_desc']}，前端已经做出约束,一般情况下客户端OK"
            )
        )
        for use_data in data["defect_cases"]
    ]

    @pytest.mark.parametrize("case", defect_params)
    @allure.title("{case[name]}")
    def test_add_defect(self, creat_user, case):
        """已知缺陷用例（xfail）：期望业务层正常拦截，实际表现为 500 泄漏或假成功，断言记录缺陷现状。"""
        # 缺陷场景：按数据文件期望的业务返回码断言，实际行为与期望不符时由 xfail 标记记录已知缺陷
        resp, _, _ = creat_user(**case["payload"])

        assert resp.status_code == 200
        assert resp.json()["code"] == case["expected_code"]

    @allure.title("添加用户，备注刚好500个字符")
    def test_add_remark_500(self, creat_user, mysql):
        """边界值验证：备注恰好 500 字符创建成功，DB 校验 remark 实际存储 500 字符（varchar(500) 上限）。"""
        # 边界值构造：remark 恰好 500 字符，命中 DB varchar(500) 上限，验证存储不截断不报错
        resp, ID, _ = creat_user(remark="a" * 500)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # DB 校验：以 char_length 统计 remark 实际存储字符数，确认 500 字符完整落库
        row = mysql["one"]("select char_length(remark) as r from sys_user where user_id = %s", (ID,))
        assert row["r"] == 500

    @pytest.mark.xfail(reason="添加用户时备注超过500字符未做长度校验，返回500并泄漏SQL/表结构，正常应返回601且不泄漏")
    @allure.title("添加用户，备注超过500个字符")
    def test_add_remark_501(self, creat_user, mysql):
        """已知缺陷（xfail）：备注 501 字符应被长度校验拦截（601），实际 500 泄漏 SQL/表结构；DB 校验无该用户落库。"""
        # 缺陷复现：remark 超上限 1 字符，期望业务返回 601 且不泄漏，实际返回 500 并泄漏 SQL/表结构
        resp, ID, _ = creat_user(remark="a" * 501)
        assert resp.status_code == 200
        assert resp.json()["code"] == 601
        assert resp.json()["success"] == False
        # DB 校验：插入应整体失败，sys_user 中不存在该 userId 的记录
        row = mysql["one"]("select count as c from sys_user where user_id = %s", (ID,))
        assert row["c"] == 0
