"""
DeptApi：部门模块接口封装。

覆盖接口（统一前缀 /system/dept）：
    list（非分页，数据位于 data 数组）/ list/exclude/{id}（编辑下拉树，
    排除指定部门及其子孙）/ {id} 详情 / creat / update / updateSort（批量保存排序）/
    delete（批量逗号分隔）

设计要点：
    - 部门 list 为【非分页】接口（与菜单模块同款），响应数据位于 data 数组
    - 新增部门 parentId 必须传有效且状态正常的父部门：
        后端需取父部门记录拼接 ancestors 祖先链，父部门不存在时抛
        AttributeError 并返回 HTTP 500（已记录为已知缺陷）
    - 删除为软删除（del_flag='2'）：存在子部门或已分配用户时返回业务码 601
      （ServiceWarning，而非 HTTP 500）
    - updateSort 与菜单模块同款（两个逗号分隔字符串），其参数异常场景已在
      菜单模块用例覆盖，本模块不重复设计（跨模块去重）
"""
class DeptApi:
    """部门模块接口封装：URL 与认证头统一集中管理，用例层仅传业务参数。"""

    def __init__(self, client, token):
        self.client = client
        # 统一组装认证头：部门模块所有接口均需携带登录后获取的 token
        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    # ===== 查询类接口：列表 / 编辑下拉树 / 详情 =====
    def list(self, **params):
        """部门列表（非分页）：支持 deptName/status/deptId 筛选，响应数据位于 data 数组。"""
        return self.client.get(
            "system/dept/list",
            headers=self.headers,
            params=params
        )

    def exclude_list(self, dept_id):
        """编辑部门下拉树：排除指定部门及其全部子孙部门。"""
        return self.client.get(
            f"system/dept/list/exclude/{dept_id}",
            headers=self.headers
        )

    def detail(self, dept_id):
        """部门详情。"""
        return self.client.get(
            f"system/dept/{dept_id}",
            headers=self.headers
        )

    # ===== 管理类接口：新增 / 编辑 / 批量排序 / 删除 =====
    def creat(self, **data):
        """新增部门：data 需含 deptName/orderNum/parentId（父部门须存在且状态正常）。"""
        return self.client.post(
            "system/dept",
            headers=self.headers,
            json=data
        )

    def update(self, **data):
        """编辑部门：data 需含 deptId 及待修改字段。"""
        return self.client.put(
            "system/dept",
            headers=self.headers,
            json=data
        )

    def update_sort(self, dept_ids, order_nums):
        """批量保存部门显示顺序：dept_ids/order_nums 为逗号分隔字符串，按下标一一对应。"""
        return self.client.put(
            "system/dept/updateSort",
            headers=self.headers,
            json={
                "deptIds": dept_ids,
                "orderNums": order_nums
            }
        )

    def delete(self, dept_ids):
        """删除部门（软删除 del_flag='2'）：支持逗号分隔批量；存在子部门或已分配用户时返回业务码 601。"""
        return self.client.delete(
            f"system/dept/{dept_ids}",
            headers=self.headers
        )
