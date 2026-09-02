"""菜单模块-冒烟 测试用例。

覆盖接口：
    POST   /system/menu          新增菜单：创建目录(M)/菜单(C)/按钮(F) 三级结构节点
    GET    /system/menu/list     菜单列表：非分页接口，返回 data 数组，含全部层级节点
    PUT    /system/menu          编辑菜单：修改名称、路由、排序、状态、可见性与权限标识
    GET    /system/menu/{id}     菜单详情：按 menuId 返回单个菜单的完整字段
    DELETE /system/menu/{ids}    删除菜单：支持逗号分隔批量删除

测试策略：
    正向主链路闭环：目录(M) → 菜单(C) → 按钮(F) 三级结构全生命周期，
    依次覆盖新增、列表层级校验、编辑、详情复查、删除五个环节。
    写后读校验：新增后通过列表与 sys_menu 表核对层级关系与落库字段，
    编辑后通过详情接口与数据库双重复查，删除后通过列表与数据库确认彻底不可见。
    数据库校验：mysql 夹具核对 sys_menu 落库字段（menu_type/parent_id 层级一致性、
    path/perms/status/visible/order_num/remark 等字段契约），验证写入真实生效。
    用例顺序依赖：各级节点 menuId 由前置用例查询并登记到类变量，后续用例复用，
    因此本类用例必须按定义顺序执行，不可单独或乱序运行。
    清理策略：删除用例按按钮 → 菜单 → 目录的子级优先顺序执行，
    避免父级先删触发「存在子菜单」业务校验，并保证测试数据零残留。
"""

import pytest
import allure
import time


@pytest.mark.menu
@pytest.mark.smoke
@allure.feature("菜单模块")
class TestMenuSmoke:
    """冒烟用例：验证目录(M) → 菜单(C) → 按钮(F) 三级菜单结构从创建到删除的完整正向生命周期。"""

    # 三级结构测试数据：目录(M) → 菜单(C) → 按钮(F) 的名称与路由以毫秒时间戳后缀保证唯一，
    # 避免与种子数据或历史运行残留相互冲突；menuId 由用例运行时查询登记，供后续用例复用
    dir_name = f"dir_{int(time.time() * 1000)}"
    menu_name = f"menu_{int(time.time() * 1000)}"
    btn_name = f"btn_{int(time.time() * 1000)}"
    dir_path = f"/dir_{int(time.time() * 1000)}"
    menu_path = f"/menu_{int(time.time() * 1000)}"
    dir_id = None
    menu_id = None
    btn_id = None

    @allure.story("新增菜单接口")
    @allure.title("添加目录、菜单、按钮三级结构成功")
    def test_menu_add_three_levels(self, menu_api, mysql):
        """验证三级菜单结构新增成功：目录(M) → 菜单(C) → 按钮(F) 逐级挂载，
        且 sys_menu 表落库字段与提交数据逐项一致。"""
        # 1) 新增顶级目录（M）：parentId=0 表示根节点，path 以 / 开头，
        #    作为前端路由访问路径的组成部分
        resp = menu_api.creat(
            **{
                "menuName": TestMenuSmoke.dir_name,
                "parentId": 0,
                "orderNum": 1,
                "path": TestMenuSmoke.dir_path,
                "menuType": "M",
                "visible": "0",
                "status": "0",
                "icon": "tree",
                "remark": "冒烟测试目录"
            }
        )
        # 断言新增成功契约：业务 code 200 + 提示「新增成功」
        assert resp.json()["msg"] == "新增成功"
        assert resp.json()['code'] == 200

        # 2) 新增子级菜单（C）前必须先取得目录 ID：parentId 需要真实的父级 menuId，
        #    按名称精确过滤列表数据取回目录 ID 并登记到类变量，供后续用例复用
        TestMenuSmoke.dir_id = [
            row["menuId"] for row in menu_api.list(
                menuName=TestMenuSmoke.dir_name
            ).json()["data"]
            if row["menuName"] == TestMenuSmoke.dir_name
        ][0]
        resp = menu_api.creat(
            **{
                "menuName": TestMenuSmoke.menu_name,
                "parentId": TestMenuSmoke.dir_id,
                "orderNum": 1,
                "path": TestMenuSmoke.menu_path,
                "component": "system/user/index",
                "menuType": "C",
                "visible": "0",
                "status": "0",
                "perms": "system:smoke:list",
                "icon": "user",
                "remark": "冒烟测试菜单"
            }
        )
        # 断言新增成功契约：业务 code 200 + 提示「新增成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "新增成功"

        # 3) 新增按钮（F）：按钮不参与前端路由，故不传 path/component，
        #    仅声明权限标识 perms 供按钮级权限控制使用；同样先查询父级菜单 ID
        TestMenuSmoke.menu_id = [
            row["menuId"] for row in menu_api.list(
                menuName=TestMenuSmoke.menu_name
            ).json()["data"]
            if row["menuName"] == TestMenuSmoke.menu_name
        ][0]
        resp = menu_api.creat(
            **{
                "menuName": TestMenuSmoke.btn_name,
                "parentId": TestMenuSmoke.menu_id,
                "orderNum": 1,
                "menuType": "F",
                "visible": "0",
                "status": "0",
                "perms": "system:smoke:add",
                "remark": "冒烟测试按钮"
            }
        )
        # 断言新增成功契约：业务 code 200 + 提示「新增成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "新增成功"
        # 数据库校验：mysql 夹具按名称查询 sys_menu 表，核对三级节点的落库字段
        # （menu_type/parent_id/path/perms/status/visible/order_num/remark）
        # 与提交数据逐字段一致，验证写入契约而非仅验证接口返回成功
        rows = mysql["all"](
            "select menu_name,menu_type,parent_id,path,perms,status,visible,order_num,remark "
            "from sys_menu where menu_name in (%s,%s,%s)",
            (TestMenuSmoke.dir_name, TestMenuSmoke.menu_name, TestMenuSmoke.btn_name)
        )
        assert len(rows) == 3
        by_name = {r["menu_name"]: r for r in rows}
        # 目录断言：menu_type=M 且 parent_id=0（顶级），path/status/visible/order_num/remark 与提交一致
        dir_db = by_name[TestMenuSmoke.dir_name]
        assert dir_db["menu_type"] == "M" and dir_db["parent_id"] == 0
        assert dir_db["path"] == TestMenuSmoke.dir_path
        assert dir_db["status"] == "0" and dir_db["visible"] == "0"
        assert dir_db["order_num"] == 1 and dir_db["remark"] == "冒烟测试目录"
        # 菜单断言：menu_type=C 且 parent_id 指向目录 ID，path/perms/remark/status/visible 与提交一致
        menu_db = by_name[TestMenuSmoke.menu_name]
        assert menu_db["menu_type"] == "C" and menu_db["parent_id"] == TestMenuSmoke.dir_id
        assert menu_db["path"] == TestMenuSmoke.menu_path
        assert menu_db["perms"] == "system:smoke:list" and menu_db["remark"] == "冒烟测试菜单"
        assert menu_db["status"] == "0" and menu_db["visible"] == "0"
        # 按钮断言：menu_type=F 且 parent_id 指向菜单 ID，perms/remark/status/visible 与提交一致
        btn_db = by_name[TestMenuSmoke.btn_name]
        assert btn_db["menu_type"] == "F" and btn_db["parent_id"] == TestMenuSmoke.menu_id
        assert btn_db["perms"] == "system:smoke:add" and btn_db["remark"] == "冒烟测试按钮"
        assert btn_db["status"] == "0" and btn_db["visible"] == "0"

    @allure.story("列表查询菜单接口")
    @allure.title("列表查询三级菜单均存在且层级正确")
    def test_menu_list_three_levels(self, menu_api):
        """验证列表接口返回三级菜单节点且层级关系正确：目录为顶级、菜单挂目录下、按钮挂菜单下。"""
        resp = menu_api.list()
        # 断言列表接口调用成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()['code'] == 200
        assert resp.json()["success"] is True
        data = resp.json()["data"]

        # 目录断言：名称唯一命中，menuType=M、parentId=0（顶级），path 与创建时一致
        dir_row = [row for row in data if row["menuName"] == TestMenuSmoke.dir_name]
        assert len(dir_row) == 1
        assert dir_row[0]["menuType"] == "M"
        assert dir_row[0]["parentId"] == 0
        assert dir_row[0]["path"] == TestMenuSmoke.dir_path

        # 菜单断言：名称唯一命中，menuType=C、parentId 指向目录 ID，path 与创建时一致
        menu_row = [row for row in data if row["menuName"] == TestMenuSmoke.menu_name]
        assert len(menu_row) == 1
        assert menu_row[0]["menuType"] == "C"
        assert menu_row[0]["parentId"] == TestMenuSmoke.dir_id
        assert menu_row[0]["path"] == TestMenuSmoke.menu_path

        # 按钮断言：名称唯一命中，menuType=F、parentId 指向菜单 ID，权限标识正确
        btn_row = [row for row in data if row["menuName"] == TestMenuSmoke.btn_name]
        assert len(btn_row) == 1
        assert btn_row[0]["menuType"] == "F"
        assert btn_row[0]["parentId"] == TestMenuSmoke.menu_id
        assert btn_row[0]["perms"] == "system:smoke:add"

        # 登记按钮 menuId 到类变量：供后续编辑/删除用例定位目标节点
        TestMenuSmoke.btn_id = btn_row[0]["menuId"]

    @allure.story("编辑菜单接口")
    @allure.title("编辑按钮、菜单、目录成功")
    def test_menu_edit_three_levels(self, menu_api, mysql):
        """验证按钮、菜单、目录三级节点均可编辑成功，且编辑后的字段变更在 sys_menu 表落库生效。"""
        # 1) 编辑按钮（F）：修改名称、权限标识与备注，层级与展示字段保持不变
        resp = menu_api.update(
            **{
                "menuId": TestMenuSmoke.btn_id,
                "menuName": f"update_{TestMenuSmoke.btn_name}",
                "parentId": TestMenuSmoke.menu_id,
                "orderNum": 1,
                "menuType": "F",
                "visible": "0",
                "status": "0",
                "perms": "system:smoke:add_edit",
                "remark": "编辑按钮"
            }
        )
        # 断言编辑成功契约：业务 code 200 + 提示「更新成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "更新成功"

        # 2) 编辑菜单（C）：状态改为停用(status=1)、可见性改为隐藏(visible=1)，
        #    验证展示类字段可独立更新而不影响层级挂载关系
        resp = menu_api.update(
            **{
                "menuId": TestMenuSmoke.menu_id,
                "menuName": TestMenuSmoke.menu_name,
                "parentId": TestMenuSmoke.dir_id,
                "orderNum": 1,
                "path": TestMenuSmoke.menu_path,
                "component": "system/user/index",
                "menuType": "C",
                "visible": "1",
                "status": "1",
                "perms": "system:smoke:list",
                "icon": "user"
            }
        )
        # 断言编辑成功契约：业务 code 200 + 提示「更新成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "更新成功"

        # 3) 编辑目录（M）：修改路由 path 与显示顺序 orderNum，验证顶级节点的路由类字段可更新
        resp = menu_api.update(
            **{
                "menuId": TestMenuSmoke.dir_id,
                "menuName": TestMenuSmoke.dir_name,
                "parentId": 0,
                "orderNum": 2,
                "path": f"update_{TestMenuSmoke.dir_path}",
                "menuType": "M",
                "visible": "0",
                "status": "0",
                "icon": "tree",
            }
        )
        # 断言编辑成功契约：业务 code 200 + 提示「更新成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "更新成功"
        # 数据库校验：mysql 夹具按 menu_id 逐一核对三个节点的编辑结果，
        # 验证名称/权限/备注/状态/可见性/排序/路由等字段确实落库变更
        btn_db = mysql["one"](
            "select menu_name,perms,remark from sys_menu where menu_id=%s",
            (TestMenuSmoke.btn_id,)
        )
        assert btn_db["menu_name"] == f"update_{TestMenuSmoke.btn_name}"
        assert btn_db["perms"] == "system:smoke:add_edit"
        assert btn_db["remark"] == "编辑按钮"
        # 菜单断言：名称保持不变，status/visible 已更新为停用与隐藏
        menu_db = mysql["one"](
            "select menu_name,status,visible from sys_menu where menu_id=%s",
            (TestMenuSmoke.menu_id,)
        )
        assert menu_db["menu_name"] == TestMenuSmoke.menu_name
        assert menu_db["status"] == "1"
        assert menu_db["visible"] == "1"
        # 目录断言：名称保持不变，orderNum 与 path 已更新
        dir_db = mysql["one"](
            "select menu_name,order_num,path from sys_menu where menu_id=%s",
            (TestMenuSmoke.dir_id,)
        )
        assert dir_db["menu_name"] == TestMenuSmoke.dir_name
        assert dir_db["order_num"] == 2
        assert dir_db["path"] == f"update_{TestMenuSmoke.dir_path}"

    @allure.story("详细查询菜单接口")
    @allure.title("详细查询三级菜单均与编辑后内容一致")
    def test_menu_detail_three_levels(self, menu_api):
        """验证详情接口返回的三级节点内容与编辑后状态一致，确认编辑结果经详情链路可读。"""
        # 1) 按钮详查：核对编辑后的名称、权限标识、备注
        detail = menu_api.detail(TestMenuSmoke.btn_id).json()["data"]
        assert detail["menuName"] == f"update_{TestMenuSmoke.btn_name}"
        assert detail["perms"] == "system:smoke:add_edit"
        assert detail["remark"] == "编辑按钮"

        # 2) 菜单详查：核对编辑后的名称、停用状态、隐藏可见性
        detail = menu_api.detail(TestMenuSmoke.menu_id).json()["data"]
        assert detail["menuName"] == TestMenuSmoke.menu_name
        assert detail["status"] == "1"
        assert detail["visible"] == "1"

        # 3) 目录详查：核对编辑后的名称、路由路径、显示顺序
        detail = menu_api.detail(TestMenuSmoke.dir_id).json()["data"]
        assert detail["menuName"] == TestMenuSmoke.dir_name
        assert detail["path"] == f"update_{TestMenuSmoke.dir_path}"
        assert detail["orderNum"] == 2

    @allure.story("删除菜单接口")
    @allure.title("删除按钮、菜单、目录成功并复查全部查不到")
    def test_menu_delete_three_levels(self, menu_api, mysql):
        """验证三级菜单删除成功：按按钮 → 菜单 → 目录的子级优先顺序删除，
        删除后列表与数据库均不可见，形成写后读闭环。"""
        # 1) 删除按钮：必须优先删除子级节点，否则父级删除将触发「存在子菜单」业务校验（601）
        resp = menu_api.delete(TestMenuSmoke.btn_id)
        # 断言删除成功契约：业务 code 200 + 提示「删除成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "删除成功"
        # 2) 删除菜单
        resp = menu_api.delete(TestMenuSmoke.menu_id)
        # 断言删除成功契约：业务 code 200 + 提示「删除成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "删除成功"
        # 3) 删除目录
        resp = menu_api.delete(TestMenuSmoke.dir_id)
        # 断言删除成功契约：业务 code 200 + 提示「删除成功」
        assert resp.json()['code'] == 200
        assert resp.json()["msg"] == "删除成功"

        # 4) 列表复查闭环：按编辑后的名称过滤，三级节点均不应再出现在列表数据中
        for name in (f"update_{TestMenuSmoke.btn_name}",
                     f"update_{TestMenuSmoke.menu_name}",
                     f"update_{TestMenuSmoke.dir_name}"):
            rows = menu_api.list(menuName=name).json()["data"]
            assert not [row for row in rows if row["menuName"] == name]
        # 数据库复查：mysql 夹具统计三个 menuId 在 sys_menu 中的记录数为 0，
        # 确认删除为物理删除且无孤儿残留，测试数据零污染
        row = mysql["one"](
            "select count(*) as cnt from sys_menu where menu_id in (%s,%s,%s)",
            (TestMenuSmoke.btn_id, TestMenuSmoke.menu_id, TestMenuSmoke.dir_id)
        )
        assert row["cnt"] == 0
