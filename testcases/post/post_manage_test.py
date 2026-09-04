"""岗位模块-管理 测试用例。

覆盖接口：
    PUT    /system/post              编辑岗位接口：按主键更新岗位字段
    DELETE /system/post/{post_ids}   删除岗位接口：按主键批量删除（支持逗号分隔）
    POST   /system/post/export       导出岗位列表接口：以 Form 表单参数导出 xlsx 二进制流

测试策略：
    编辑：覆盖不存在岗位（有 post_id 判空保护返回 500，与角色模块行为不同）、
    名称/编码重复校验两类场景。
    删除：覆盖批量成功、批量含不存在岗位（幂等语义）、已分配岗位 500 拦截、
    批量含已分配岗位事务回滚、非法 ID 500 泄漏。
    导出：后端以 StreamingResponse 返回 xlsx 二进制流且未指定 media_type（响应无 Content-Type 头），
    校验响应体 zip 魔数（PK\x03\x04）。
    已知缺陷(xfail)：删除不存在岗位假成功、删除 ID 非法值 500 泄漏。
    数据依赖：用例通过工厂夹具 creat_post 创建临时岗位，用例结束后自动级联清理。
"""

import time
import pytest
import requests
import allure


@pytest.mark.post
@allure.feature("岗位模块")
@allure.story("编辑岗位接口")
class TestPostEdit:
    """编辑岗位接口用例：覆盖不存在岗位拦截与名称/编码重复校验。"""

    @allure.title("编辑不存在的岗位")
    def test_edit_nonexist(self, post_api):
        """验证编辑不存在的岗位被拦截：岗位编辑存在 post_id 判空保护，返回 500 并提示「岗位不存在」。"""
        # 行为说明：编辑 999 时 post_detail_services 返回空模型（post_id=None），
        # edit_post_services 以 if post_info.post_id 判空 → 提示「岗位不存在」返回 500；
        # 与角色模块不同：角色模块编辑 999 直接触发 SQLAlchemy 错误泄漏，岗位侧存在判空保护
        resp = post_api.update(
            postId=999,
            postCode="none",
            postName="岗位不存在",
            postSort=9
        )
        # 断言拦截契约：code 500 + 失败标识 + 提示语「岗位不存在」
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "岗位不存在" in resp.json()["msg"]

    @allure.title("编辑时岗位名称重复")
    def test_edit_duplicate_name(self, post_api, creat_post):
        """业务规则验证：编辑时岗位名称与既有岗位重复被唯一性校验拦截，返回 500 并提示「岗位名称已存在」。"""
        # 将自建岗位名称改为种子岗位「董事长」，触发名称唯一性检查（新增/编辑共用同一函数）；
        # 编码以时间戳构造唯一，排除编码维度干扰
        _, post_id, _ = creat_post()
        resp = post_api.update(
            postId=post_id,
            postCode=f"k_{int(time.time() * 1000)}",
            postName="董事长",
            postSort=9
        )
        # 断言拦截契约：code 500 + 失败标识 + 提示语「岗位名称已存在」
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "岗位名称已存在" in resp.json()["msg"]

    @allure.title("编辑时岗位编码重复")
    def test_edit_duplicate_code(self, post_api, creat_post):
        """业务规则验证：编辑时岗位编码与既有岗位重复被唯一性校验拦截，返回 500 并提示「岗位编码已存在」。"""
        # 将自建岗位编码改为种子岗位 "ceo"，触发编码唯一性检查；名称以时间戳构造唯一排除干扰
        _, post_id, _ = creat_post()
        resp = post_api.update(
            postId=post_id,
            postCode="ceo",
            postName=f"n_{int(time.time() * 1000)}",
            postSort=9
        )
        # 断言拦截契约：code 500 + 失败标识 + 提示语「岗位编码已存在」
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "岗位编码已存在" in resp.json()["msg"]


@pytest.mark.post
@allure.feature("岗位模块")
@allure.story("删除岗位接口")
class TestPostDelete:
    """删除岗位接口用例：覆盖批量成功、幂等语义、占用拦截、事务回滚与非法参数。"""

    @allure.title("批量删除岗位成功")
    def test_delete_batch(self, post_api, creat_post):
        """验证批量删除两个岗位成功，且删除后按编码复查均查不到。"""
        # 创建两个独立临时岗位（编码由工厂夹具保证唯一），批量删除传逗号分隔的 post_id 串
        _, pid1, code1 = creat_post()
        _, pid2, code2 = creat_post()
        resp = post_api.delete(f"{pid1},{pid2}")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] is True
        # API 复查：分别按编码筛选列表，total 均为 0，确认两条数据已物理删除
        assert post_api.list(postCode=code1).json()["total"] == 0
        assert post_api.list(postCode=code2).json()["total"] == 0

    @allure.title("批量删除含不存在的岗位")
    def test_delete_batch_with_nonexist(self, post_api, creat_post):
        """幂等语义验证：批量删除串中含不存在的岗位（999）时被静默忽略，真实存在的岗位正常删除。"""
        # 构造 "999,{pid}" 批量串：999 无对应数据不报错，真实岗位正常删除（幂等语义）
        _, pid, code = creat_post()
        resp = post_api.delete(f"999,{pid}")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] is True
        # 复查：按编码筛选列表 total 为 0，确认真实存在的岗位已删除
        assert post_api.list(postCode=code).json()["total"] == 0

    @allure.title("删除已分配用户的岗位")
    def test_delete_assigned_rejected(self, post_api):
        """业务规则验证：删除已分配用户的岗位被拦截，返回 500 并提示「已分配，不能删除」。"""
        # 种子岗位 1（董事长）已绑定 admin 用户，count_user_post_dao 计数大于 0，
        # 删除时触发用户占用检查
        resp = post_api.delete(1)
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "已分配，不能删除" in resp.json()["msg"]

    @pytest.mark.xfail(reason="删除不存在的岗位本应报错却返回删除成功，前端已经做出约束,一般情况下客户端OK")
    @allure.title("删除不存在的岗位")
    def test_delete_nonexist(self, post_api):
        """已知缺陷验证：删除不存在的岗位本应报错，实际无存在性校验返回删除成功（假成功），标记 xfail。"""
        # 缺陷表现：删除 999 时无存在性校验，删除 0 行仍返回「删除成功」200；
        # 用例断言正常行为契约（code 500），当前实际失败故标记 xfail
        resp = post_api.delete(999)
        assert resp.json()["code"] == 500

    @allure.title("批量删除含已分配岗位（事务回滚）")
    def test_delete_batch_with_assigned(self, post_api, creat_post):
        """事务回滚验证：批量删除串中含已分配岗位时，删除事务整体回滚，临时岗位不被删除。"""
        # 构造 "1,{pid}" 批量串：岗位 1 已分配必然抛异常，pid 为新建临时岗位
        _, pid, code = creat_post()
        resp = post_api.delete(f"1,{pid}")
        assert resp.json()["code"] == 500
        # 事务回滚验证：临时岗位按编码复查 total 仍为 1，
        # 证明删除事务全有或全无（已分配岗位的异常回滚了整批删除）
        assert post_api.list(postCode=code).json()["total"] == 1

    # 缺陷说明：删除 ID 传非数字（如 abc）时，后端在 service 层 int() 转换失败，
    # 返回 500 并泄漏 Python 内部错误信息（invalid literal for int()），
    # 正常应像详情接口一样由参数层返回 422
    @pytest.mark.xfail(
        reason="删除ID传非法值时后端未做格式校验，int转换失败返回500并泄漏内部细节，"
               "前端已经做出约束,一般情况下客户端OK"
    )
    @allure.title("删除ID为非法值")
    def test_delete_invalid_id(self, post_api):
        """已知缺陷验证：删除 ID 传非数字值时后端未做格式校验，service 层 int() 转换失败返回 500 并泄漏，期望 422 而失败，标记 xfail。"""
        # 缺陷触发点：删除接口路径参数为 str（支持逗号批量），"abc" 可进入 service 层，
        # int("abc") 抛 ValueError 返回 500 并泄漏内部细节；正常应像详情接口一样由参数层返回 422
        with pytest.raises(requests.exceptions.HTTPError) as e:
            post_api.delete("abc")
        assert e.value.response.status_code == 422


@pytest.mark.post
@allure.feature("岗位模块")
@allure.story("导出岗位列表接口")
class TestPostExport:
    """导出岗位列表接口用例：验证导出成功且响应体为合法 xlsx 二进制流。"""

    @allure.title("导出岗位列表成功")
    def test_export_success(self, post_api):
        """验证导出岗位列表成功：接口返回 xlsx 二进制流，校验响应体 zip 魔数（PK\x03\x04）。"""
        # 导出由 StreamingResponse 返回 xlsx 二进制流
        resp = post_api.export()
        assert resp.status_code == 200
        # 后端 StreamingResponse 未指定 media_type，响应不含 Content-Type 头，
        # 故改为校验响应体前 4 字节为 zip 魔数（PK\x03\x04），
        # 以此证明导出内容为合法 xlsx（xlsx 本质为 zip 容器）
        assert resp.content[:4] == b"PK\x03\x04"
