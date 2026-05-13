# 天机 六爻排盘

六爻预测系统是一个本地运行的六爻排盘与历史记录管理工具。项目提供 Web 页面用于录入起卦信息、生成排盘结果、保存记录、查询历史记录，并支持备注维护、复制文本、下载文本和保存图片。

当前版本已经移除 MySQL 依赖，改为使用 Python 内置的 SQLite 数据库。数据库文件默认保存在项目目录下的 `liuyao.sqlite3`，应用启动时会自动初始化数据库和当前年份表。因此项目可以作为一个开箱即用的本地工具复制到任意目录运行。

## 功能特性

- 支持三种起卦方式：指定六爻、多随机、单随机
- 支持手动输入公历日期、时分、月柱和日柱干支
- 自动生成六爻排盘结果，包括主卦、变卦、六神、世应、动爻等信息
- 支持保存排盘结果、标的、用户和备注
- 支持按年份、日期、标的、用户查询历史记录
- 支持查看历史排盘，并在历史记录中更新备注或删除记录
- 支持复制排盘文本、下载文本、保存排盘图片
- 使用本地 SQLite 数据库，无需安装数据库服务
- 项目目录迁移后可直接运行，数据库随项目文件一起迁移

## 技术栈

| 层级 | 技术 |
| --- | --- |
| Web 框架 | Flask |
| 页面模板 | Jinja2 / HTML / CSS / JavaScript |
| 数据库 | SQLite |
| 数据库驱动 | Python 标准库 `sqlite3` |
| 排盘依赖 | `sxtwl` |
| 图片导出 | `html2canvas` |
| 运行环境 | Python 3.10+ |

## 项目架构

项目采用轻量分层结构，核心逻辑、Web 接口、数据库访问和页面模板相互分离。

```text
.
├── main.py              # 项目启动入口
├── web_app.py           # Flask 应用、页面路由和保存/查询接口
├── db.py                # SQLite 连接、数据库初始化、年份表创建
├── config.py            # 数据库路径配置
├── divination.py        # 六爻排盘核心逻辑
├── data.py              # 卦象、干支、六亲、六神等基础数据
├── requirements.txt     # Python 依赖
├── liuyao.sqlite3       # 本地 SQLite 数据库文件，首次运行后自动生成
└── templates/
    ├── index.html       # 排盘主页面
    └── history.html     # 历史记录查询页面
```

## 核心模块说明

### `main.py`

项目推荐启动入口。它只负责调用 `web_app.py` 中的 `run_web()`，让用户启动项目时不需要关心 Flask 内部结构。

### `web_app.py`

Web 应用主模块，负责：

- 初始化 Flask 应用
- 应用启动时调用数据库初始化
- 渲染排盘主页 `/`
- 处理排盘表单提交
- 保存排盘记录 `/save`
- 查询历史记录 `/history`
- 查看历史排盘 `/history/view/<year>/<id>`
- 更新历史备注 `/update_remarks`

### `db.py`

SQLite 数据访问模块，负责：

- 根据配置路径创建或连接数据库
- 设置 `sqlite3.Row`，让查询结果可以按字段名读取
- 自动创建年份表
- 安全转义 SQLite 表名
- 提供 `initialize_database()`，在应用启动时自动准备数据库

### `config.py`

数据库路径配置模块。默认数据库路径为：

```text
项目目录/liuyao.sqlite3
```

也可以通过环境变量 `LIUYAO_DB_PATH` 指定自定义数据库位置。

### `divination.py` 和 `data.py`

排盘业务模块。

- `divination.py` 负责把用户输入转换成排盘结果
- `data.py` 存放卦象、干支、六亲、六神等基础数据

### `templates/`

前端页面模板目录。

- `index.html` 是排盘主界面
- `history.html` 是历史记录查询界面

## 数据库设计

项目使用 SQLite 单文件数据库。默认文件名：

```text
liuyao.sqlite3
```

数据库采用按年份分表的方式保存历史记录，表名格式为：

```text
YYYY年
```

例如：

```text
2026年
```

应用启动时会自动创建当前年份表；保存记录时，如果记录所属年份表不存在，也会自动创建。

### 年份表字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 自增主键 |
| `起卦方式` | TEXT | 指定、多随机、单随机 |
| `时间` | TEXT | 标准格式为 `YYYY-MM-DD HH:MM` |
| `月干` | TEXT | 月柱天干 |
| `月支` | TEXT | 月柱地支 |
| `日干` | TEXT | 日柱天干 |
| `日支` | TEXT | 日柱地支 |
| `初爻` | TEXT | 初爻编码 |
| `二爻` | TEXT | 二爻编码 |
| `三爻` | TEXT | 三爻编码 |
| `四爻` | TEXT | 四爻编码 |
| `五爻` | TEXT | 五爻编码 |
| `上爻` | TEXT | 上爻编码 |
| `标的` | TEXT | 求测事项或标的名称 |
| `用户` | TEXT | 保存记录的用户 |
| `备注` | TEXT | 备注内容 |

爻值编码：

| 编码 | 含义 |
| --- | --- |
| `1` | 少阳 |
| `2` | 少阴 |
| `3` | 老阳 |
| `4` | 老阴 |

## 安装与运行

### 1. 安装 Python

建议使用 Python 3.10 或更高版本。

确认 Python 可用：

```powershell
python --version
```

### 2. 安装依赖

在项目目录执行：

```powershell
pip install -r requirements.txt
```

如果希望使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. 启动项目

```powershell
python main.py
```

启动后访问：

```text
http://127.0.0.1:5000
```

启动时程序会自动准备数据库，不需要额外运行建库脚本。

## 部署方式

### 本地桌面使用

最简单的部署方式是直接复制整个项目目录，然后在目录中运行：

```powershell
python main.py
```

适合个人电脑、本地工作台或离线环境使用。

### 迁移到其他目录或电脑

迁移时复制以下内容：

```text
项目源码
liuyao.sqlite3
```

在新位置安装依赖后运行：

```powershell
pip install -r requirements.txt
python main.py
```

如果 `liuyao.sqlite3` 不存在，程序会自动创建一个新的空数据库。如果要保留历史记录，请确保迁移时带上原来的 `liuyao.sqlite3`。

### 自定义数据库位置

默认数据库文件放在项目目录下。如果希望把数据放在单独的数据目录，可以设置 `LIUYAO_DB_PATH`。

PowerShell 示例：

```powershell
$env:LIUYAO_DB_PATH = "D:\data\liuyao.sqlite3"
python main.py
```

设置后，程序会使用该路径的 SQLite 文件；如果文件不存在，会自动创建。

### 局域网访问

当前 `web_app.py` 默认监听 `127.0.0.1:5000`，只允许本机访问。如果需要局域网内其他设备访问，可以把 `run_web()` 中的 Flask 启动参数调整为：

```python
app.run(host="0.0.0.0", port=5000, debug=False)
```

然后在同一局域网设备上访问：

```text
http://本机局域网IP:5000
```

注意：这是本地工具项目，默认没有登录鉴权。开放到局域网前请确认网络环境可信。

## 备份与恢复

所有历史记录都保存在 SQLite 文件中：

```text
liuyao.sqlite3
```

备份时复制这个文件即可。

恢复时把备份文件放回项目目录，或通过 `LIUYAO_DB_PATH` 指向备份文件路径。

## 常见问题

### 是否还需要 MySQL？

不需要。项目已经改为 SQLite，本地运行无需安装 MySQL，也无需创建数据库用户。

### 为什么第一次启动后会多出 `liuyao.sqlite3`？

这是本地数据库文件，用于保存排盘历史记录。它是项目运行所需的数据文件，不是缓存文件。

### 可以删除 `liuyao.sqlite3` 吗？

可以，但删除后历史记录会丢失。再次启动项目时会自动生成新的空数据库。

### 迁移项目时应该复制哪些文件？

如果只迁移程序，复制项目源码即可。如果要保留历史记录，需要同时复制 `liuyao.sqlite3`。

### 端口被占用怎么办？

默认端口是 `5000`。如果端口被占用，可以在 `web_app.py` 的 `run_web()` 中修改端口：

```python
app.run(debug=False, port=5001)
```
