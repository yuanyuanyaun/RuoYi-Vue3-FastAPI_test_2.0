"""
MenuApi：菜单模块接口封装。

覆盖接口（统一前缀 /system/menu）：
    list（非分页，响应数据位于 data 数组）/ treeselect（菜单树）/
    roleMenuTreeselect/{id}（指定角色的菜单树，含已选菜单 id）
    {id} 详情 / creat / update / updateSort（批量保存排序）/ delete（批量逗号分隔）

设计要点：
    - 菜单 list 为【非分页】接口：响应无 rows/total 结构，数据直接位于 data 数组，
      与用户/角色等分页模块的断言结构不同
    - updateSort 请求体为两个逗号分隔字符串（menuIds/orderNums 按下标一一对应），
      非 JSON 数组
    - 菜单类型约定：M=目录、C=菜单、F=按钮；F 按钮的 path/component 留空（不进路由）
    - 顶级菜单（parentId=0）的 path 规范上以 "/" 开头（前端路由要求）
"""
class MenuApi:
    """菜单模块接口封装：URL 与认证头统一集中管理，用例层仅传业务参数。"""

    def __init__(self, client, token):
        self.client = client
        # 统一组装认证头：菜单模块所有接口均需携带登录后获取的 token
        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    # ===== 查询类接口：列表 / 菜单树 / 角色菜单树 / 详情 =====
    def list(self, **params):
        """菜单列表（非分页）：支持 menuName/status 筛选，响应数据位于 data 数组。"""
        return self.client.get(
            "system/menu/list",
            headers=self.headers,
            params=params
        )

    def treeselect(self):
        """菜单树：完整菜单层级结构（菜单选择器数据来源）。"""
        return self.client.get(
            "system/menu/treeselect",
            headers=self.headers
        )

    def role_menu_tree(self, role_id):
        """指定角色的菜单树：标记该角色已选中的菜单 id。"""
        return self.client.get(
            f"system/menu/roleMenuTreeselect/{role_id}",
            headers=self.headers
        )

    def detail(self, menu_id):
        """菜单详情。"""
        return self.client.get(
            f"system/menu/{menu_id}",
            headers=self.headers
        )

    # ===== 管理类接口：新增 / 编辑 / 批量排序 / 删除 =====
    def creat(self, **data):
        """新增菜单：data 含 menuName/orderNum/menuType 等必填字段。"""
        return self.client.post(
            "system/menu",
            headers=self.headers,
            json=data
        )

    def update(self, **data):
        """编辑菜单：data 需含 menuId 及待修改字段。"""
        return self.client.put(
            "system/menu",
            headers=self.headers,
            json=data
        )

    def update_sort(self, menu_ids, order_nums):
        """批量保存菜单显示顺序：menu_ids/order_nums 为逗号分隔字符串，按下标一一对应。"""
        return self.client.put(
            "system/menu/updateSort",
            headers=self.headers,
            json={
                "menuIds": menu_ids,
                "orderNums": order_nums
            }
        )

    def delete(self, menu_ids):
        """删除菜单：支持逗号分隔的菜单 id 列表批量删除。"""
        return self.client.delete(
            f"system/menu/{menu_ids}",
            headers=self.headers
        )
