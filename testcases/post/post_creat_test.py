"""岗位模块-新增 测试用例。

覆盖接口：
    POST /system/post    新增岗位接口：新增岗位，返回业务 code 与新增成功提示

测试策略：
    数据驱动：加载 data/post/post_creat_data.json，按 success_cases（成功）、
    fail_code_cases（业务失败：HTTP 200 + 业务 code 601/500）、fail_status_cases
    （HTTP 状态失败：4xx/5xx）、defect_cases（已知缺陷）四组参数化执行。
    边界值：postCode 上限 64、postName 上限 50、备注上限 500，
    均覆盖恰好达标与超限 1 字符两个边界。
    业务规则：postCode/postName 唯一性校验，除编码与名称外其他字段相同可重复新增。
    已知缺陷(xfail)：缺 status、postSort 超范围、备注 501 时后端未做参数校验，
    返回 500 并泄漏内部错误。
    数据依赖：成功场景通过工厂夹具 creat_post 创建临时岗位，用例结束后自动级联清理；
    缺陷场景直接使用 client 发送原始请求体，保证「缺字段」场景真实复现。
"""

import json
import allure
import pytest
import time
import requests
from utils.function import make_post, auth

# 加载数据驱动用例数据：模块导入时执行一次，读取岗位新增场景的四组用例集，供参数化用例复用
with open("data/post/post_creat_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)
# 模块级时间戳：与边界用例配合构造唯一编码/名称，避免跨用例数据冲突
ts = str(int(time.time() * 1000))


@pytest.mark.post
@allure.feature("岗位模块")
@allure.story("添加岗位接口")
class TestPostCreat:
    """添加岗位用例：覆盖数据驱动四组场景、编码/名称唯一性、字段长度边界值与已知缺陷(xfail)。"""

    # ===== 成功场景（数据驱动）：接口返回预期 code 且返回有效 post_id =====
    @pytest.mark.parametrize("case", data["success_cases"])
    @allure.title("{case[name]}")
    def test_creat_success(self, case, creat_post):
        """验证数据驱动定义的成功场景：新增岗位返回预期业务 code，且返回有效的 post_id。"""
        # 工厂夹具 creat_post：创建成功即登记该岗位，用例结束后自动级联清理，避免残留脏数据
        resp, post_id, _ = creat_post(**case["overrides"])
        assert resp.json()["code"] == case["expected_code"]
        # 断言成功契约外，还需确认 post_id 非空（新增真实生效，而非假成功）
        assert post_id is not None

    # ===== 业务失败场景（数据驱动）：HTTP 200 + 业务 code（601 校验拦截 / 500 唯一性冲突）=====
    @pytest.mark.parametrize("case", data["fail_code_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_code(self, case, post_api):
        """验证数据驱动定义的业务失败场景：接口返回 HTTP 200 但业务 code 为预期拦截值，成功标识为 False。"""
        # 工厂函数 make_post 生成默认合法请求体，overrides 叠加场景定制
        #（如 postCode=None 模拟缺字段、postName="董事长" 模拟重复名称），
        # 保证失败场景只修改单一变量
        resp = post_api.creat(**make_post(**case["overrides"]))
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] is False

    # ===== HTTP 状态失败场景（数据驱动）：请求抛出 HTTPError，校验响应状态码 =====
    @pytest.mark.parametrize("case", data["fail_status_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_status(self, case, post_api):
        """验证数据驱动定义的 HTTP 状态失败场景：请求直接抛出 HTTPError，且状态码与用例预期一致。"""
        # 此类场景由框架层直接返回非 2xx，requests 抛出 HTTPError，
        # 故用 pytest.raises 捕获异常后断言响应状态码
        with pytest.raises(requests.exceptions.HTTPError) as e:
            post_api.creat(**make_post(**case["overrides"]))
        assert e.value.response.status_code == case["expected_status"]

    # ===== 已知缺陷场景（数据驱动，xfail）：期望正常拦截，实际 500 泄漏或假成功 =====
    defect_params = [
        pytest.param(
            use_data,
            marks=pytest.mark.xfail(
                reason=f"已知缺陷：{use_data['defect_desc']}，"
                       f"前端已经做出约束,一般情况下客户端OK"
            )
        )
        for use_data in data["defect_cases"]
    ]

    @pytest.mark.parametrize("case", defect_params)
    @allure.title("{case[name]}")
    def test_creat_defect(self, case, client, token):
        """已知缺陷验证：数据驱动定义缺字段等场景时，期望正常拦截，实际返回 500 泄漏内部错误或假成功，标记 xfail。"""
        # defect_params 将 defect_cases 逐条包装为 pytest.param 并统一打上 xfail 标记，
        # 原因串由数据中的 defect_desc 动态生成
        # 缺陷用例直接以原始 overrides 作为请求体（不叠加工厂函数默认值），
        # 保证「缺字段」场景真实复现；请求头由 auth(token) 生成携带登录凭证
        resp = client.post(
            "system/post",
            headers=auth(token),
            json=case["overrides"]
        )
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] is False

    # ===== 唯一性验证：除编码和名称外，其余字段相同可重复新增 =====
    @allure.title("除了岗位编码和岗位名称外其余字段可重复添加")
    def test_creat_code_other_fields(self, creat_post):
        """业务规则验证：岗位唯一性仅约束 postCode/postName，其余字段（排序/状态/备注）相同不影响新增。"""
        # 公共字段（排序/状态/备注）完全相同，仅编码与名称不同（均带模块级时间戳 ts 保证唯一），
        # 两次新增均应成功，证明唯一性约束只作用于编码与名称
        common = {
            "postSort": 1,
            "status": "0",
            "remark": "备注"
        }
        resp_a, _, _ = creat_post(
            **{
                **common,
                "postCode": f"a_{ts}",
                "postName": f"aa_{ts}"
            }
        )
        resp_b, _, _ = creat_post(
            **{
                **common,
                "postCode": f"b_{ts}",
                "postName": f"bb_{ts}"
            }
        )
        assert resp_a.json()["code"] == 200
        assert resp_b.json()["code"] == 200
        assert resp_a.json()["success"] is True
        assert resp_b.json()["success"] is True

    # ===== 边界值：postCode 上限 64（@Size 校验）=====
    @allure.title("岗位编码恰好 64 字符成功")
    def test_creat_code_64(self, creat_post):
        """边界值验证：岗位编码恰好 64 字符时新增成功，且返回有效的 post_id。"""
        # 构造恰好 64 字符的编码（62 个 'a' + 占位符 "1@"），命中 postCode 长度上限的正常边界
        resp, post_id, _ = creat_post(postCode="a" * 62 + "1@")
        assert resp.json()["code"] == 200
        assert post_id is not None
        assert resp.json()["success"] is True

    @allure.title("岗位编码恰好超过 64 字符")
    def test_creat_code_65(self, creat_post):
        """边界值验证：岗位编码超过 64 字符时被 @Size 校验拦截，返回业务 code 601。"""
        # 构造 65 字符编码（63 个 'a' + "1@"），超上限 1 字符，命中校验返回 601（正常行为，非缺陷）
        resp, _, _ = creat_post(postCode="a" * 63 + "1@")
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False

    # ===== 边界值：postName 上限 50（@Size 校验）=====
    @allure.title("岗位名称恰好 50 字符成功")
    def test_creat_name_50(self, creat_post):
        """边界值验证：岗位名称恰好 50 字符时新增成功，且返回有效的 post_id。"""
        # 构造恰好 50 字符的名称（48 个 'a' + "1@"），命中 postName 长度上限的正常边界
        resp, post_id, _ = creat_post(postName="a" * 48 + "1@")
        assert resp.json()["code"] == 200
        assert post_id is not None
        assert resp.json()["success"] is True

    @allure.title("岗位名称恰好超过 50 字符")
    def test_creat_name_51(self, creat_post):
        """边界值验证：岗位名称超过 50 字符时被 @Size 校验拦截，返回业务 code 601。"""
        # 构造 51 字符名称（49 个 'a' + "1@"），超上限 1 字符，命中校验返回 601
        resp, _, _ = creat_post(postName="a" * 49 + "1@")
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False

    # ===== 边界值：备注 500 成功（DB varchar(500) 上限）=====
    @allure.title("备注恰好 500 字符成功")
    def test_creat_remark_500(self, creat_post):
        """边界值验证：备注恰好 500 字符时新增成功（命中 DB varchar(500) 容量上限），且返回有效的 post_id。"""
        # 构造恰好 500 字符的备注（498 个 'a' + "1@"），命中数据库容量上限的正常边界
        resp, post_id, _ = creat_post(remark="a" * 498 + "1@")
        assert resp.json()["code"] == 200
        assert post_id is not None
        assert resp.json()["success"] is True

    # ===== 边界值：备注 501 → 500 泄漏（已知缺陷：模型层无长度校验，DB 层报错）=====
    @pytest.mark.xfail(reason="添加岗位时备注超过500字符未做长度校验，返回500并泄漏SQL/表结构，正常应返回601且不泄漏")
    def test_creat_remark_501(self, post_api):
        """已知缺陷验证：备注 501 字符时模型层无长度校验，落库触发 DB 错误返回 500 并泄漏，期望 601 而失败，标记 xfail。"""
        # 缺陷触发点：模型层未对备注做长度校验，超过 DB varchar(500) 上限后由数据库层报错，
        # 返回 500 并泄漏 SQL/表结构信息；用例断言正常行为契约（601），当前实际失败故标记 xfail；
        # 本用例直接通过 make_post 构造请求体，不依赖工厂夹具（缺陷用例不产生有效数据，无需清理）
        resp = post_api.creat(**make_post(remark="a" * 499 + "1@"))
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False
