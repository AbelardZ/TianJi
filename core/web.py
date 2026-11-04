# -*- coding: utf-8 -*-
"""Web 装配层：Flask 应用、页面路由与记录读写接口。"""

import json
import re
import webbrowser
from datetime import datetime
from threading import Timer

from flask import Flask, jsonify, redirect, render_template, request, url_for

from .config import BASE_DIR, STATIC_DIR, TEMPLATE_DIR
from .db import (
    ensure_bazi_table,
    ensure_daliuren_table,
    ensure_meihua_table,
    ensure_mingli_table,
    ensure_qimen_table,
    ensure_year_table,
    ensure_ziwei_table,
    ensure_xiaoliuren_table,
    get_connection,
    initialize_database,
    quote_identifier,
)
from modules.bazi.bazi import perform_bazi
from modules.liuyao.divination import create_wapp, perform_divination
from modules.qimen import qimen as qimen_lib
from modules.xiaoliuren import data as xlr_data
from modules.xiaoliuren.xiaoliuren import (
    SCHOOLS as XLR_SCHOOLS,
    METHODS as XLR_METHODS,
    NUM_COUNT as XLR_NUM_COUNT,
    calculate as xlr_calculate,
    summary_of as xlr_summary,
)
from modules.meihua.meihua import (
    METHODS as MH_METHODS,
    YEAR_RULES as MH_YEAR_RULES,
    TRIGRAMS as MH_TRIGRAMS,
    calculate as mh_calculate,
    summary_of as mh_summary,
)
from modules.daliuren.daliuren import (
    METHODS as DLR_METHODS,
    YUEJIANG_RULE_NAMES as DLR_YUEJIANG_RULES,
    NOBLE_RULE_NAMES as DLR_NOBLE_RULES,
    SHEHAI_RULES as DLR_SHEHAI_RULES,
    GAN as DLR_GAN,
    ZHI as DLR_ZHI,
    TIANJIANG as DLR_TIANJIANG,
    ZONGMEN_INFO,
    calculate as dlr_calculate,
    summary_of as dlr_summary,
    normalize_options as dlr_normalize_options,
)

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR),
)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_header(r):
    """禁用浏览器缓存，确保每次修改前端代码后刷新都能看到最新效果"""
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

initialize_database()

def get_available_years():
    years = []
    try:
        with get_connection() as cnx:
            tables = cnx.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            for table in tables:
                match = re.match(r'^(\d{4})年$', table["name"])
                if match:
                    years.append(match.group(1))
    except Exception as e:
        print(f"Error fetching tables: {e}")
    
    years.sort(reverse=True)
    return years


def _query_liuyao_history(year_table, search_date="", search_subject="", search_user=""):
    """查询六爻年份表历史（供页面内嵌历史列表使用）。"""
    available_years = get_available_years()
    results = []
    if year_table in available_years:
        table_name = f"{year_table}年"
        try:
            query = f"SELECT * FROM {quote_identifier(table_name)} WHERE 1=1"
            params = []
            if search_date:
                query += " AND 时间 LIKE ?"
                params.append(f"{search_date}%")
            if search_subject:
                query += " AND 标的 LIKE ?"
                params.append(f"%{search_subject}%")
            if search_user:
                query += " AND 用户 LIKE ?"
                params.append(f"%{search_user}%")
            query += " ORDER BY id DESC LIMIT 60"
            with get_connection() as cnx:
                rows = cnx.execute(query, params).fetchall()
            for row in rows:
                yaos_str = f"{row['初爻']}{row['二爻']}{row['三爻']}{row['四爻']}{row['五爻']}{row['上爻']}"
                results.append({
                    'id': row['id'],
                    'time': row['时间'],
                    'user': row['用户'],
                    'subject': row['标的'],
                    'mode': row['起卦方式'],
                    'month_gz': f"{row['月干']}{row['月支']}",
                    'day_gz': f"{row['日干']}{row['日支']}",
                    'yaos': yaos_str,
                })
        except Exception as e:
            print(f"Error querying history: {e}")
    return results, available_years


def get_bazi_records(q=""):
    """查询八字记录（供页面内记录切换使用）。"""
    records = []
    with get_connection() as cnx:
        ensure_bazi_table(cnx)
        query = "SELECT * FROM bazi_records WHERE 1=1"
        params = []
        if q:
            query += " AND (姓名 LIKE ? OR 标签 LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])
        query += " ORDER BY id DESC LIMIT 60"
        rows = cnx.execute(query, params).fetchall()
    for row in rows:
        pillars = " ".join(
            f"{row[c1]}{row[c2]}"
            for c1, c2 in [("年干", "年支"), ("月干", "月支"), ("日干", "日支"), ("时干", "时支")]
        )
        records.append({
            "id": row["id"],
            "time": row["时间"],
            "gender": row["性别"],
            "name": row["姓名"],
            "pillars": pillars,
            "tags": row["标签"] or "",
            "remarks": row["备注"] or "",
        })
    return records


def _insert_bazi_record(subject, gender, date_str_full, pillars, remarks="",
                        tags="", solar_minutes=0, hour_unknown=False):
    """写入一条八字记录，返回新记录 id。"""
    dt = datetime.strptime(date_str_full, "%Y-%m-%d %H:%M")
    if hour_unknown:
        hour_gan, hour_zhi = "", ""
    else:
        hour_gan, hour_zhi = pillars[3][0], pillars[3][1]
    with get_connection() as cnx:
        ensure_bazi_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO bazi_records
            (时间, 性别, 姓名, 年干, 年支, 月干, 月支, 日干, 日支, 时干, 时支, 备注, 标签, 校正分钟, 时柱未知)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dt.strftime("%Y-%m-%d %H:%M"),
                gender,
                subject,
                pillars[0][0], pillars[0][1],
                pillars[1][0], pillars[1][1],
                pillars[2][0], pillars[2][1],
                hour_gan, hour_zhi,
                remarks,
                tags,
                str(solar_minutes),
                "是" if hour_unknown else "否",
            ),
        )
        cnx.commit()
        return cursor.lastrowid


def _update_bazi_record(record_id, subject, gender, date_str_full, pillars,
                        remarks="", tags="", solar_minutes=0, hour_unknown=False):
    """更新一条八字记录，返回是否成功。"""
    dt = datetime.strptime(date_str_full, "%Y-%m-%d %H:%M")
    hour_gan, hour_zhi = ("", "") if hour_unknown else (pillars[3][0], pillars[3][1])
    with get_connection() as cnx:
        ensure_bazi_table(cnx)
        cursor = cnx.execute(
            """
            UPDATE bazi_records SET
                时间 = ?, 性别 = ?, 姓名 = ?, 年干 = ?, 年支 = ?,
                月干 = ?, 月支 = ?, 日干 = ?, 日支 = ?, 时干 = ?, 时支 = ?,
                备注 = ?, 标签 = ?, 校正分钟 = ?, 时柱未知 = ?
            WHERE id = ?
            """,
            (
                dt.strftime("%Y-%m-%d %H:%M"), gender, subject,
                pillars[0][0], pillars[0][1],
                pillars[1][0], pillars[1][1],
                pillars[2][0], pillars[2][1],
                hour_gan, hour_zhi, remarks, tags, str(solar_minutes),
                "是" if hour_unknown else "否", record_id,
            ),
        )
        cnx.commit()
        return cursor.rowcount > 0


@app.route('/history')
def history():
    available_years = get_available_years()
    current_year = datetime.now().strftime('%Y')
    
    year_table = request.args.get('year_table', current_year)
    search_date = request.args.get('search_date', '')
    search_subject = request.args.get('search_subject', '')
    search_user = request.args.get('search_user', '')
    
    results = []
    
    if year_table in available_years:
        table_name = f"{year_table}年"
        try:
            query = f"SELECT * FROM {quote_identifier(table_name)} WHERE 1=1"
            params = []
            
            if search_date:
                query += " AND 时间 LIKE ?"
                params.append(f"{search_date}%")
            
            if search_subject:
                query += " AND 标的 LIKE ?"
                params.append(f"%{search_subject}%")
                
            if search_user:
                query += " AND 用户 LIKE ?"
                params.append(f"%{search_user}%")
            
            query += " ORDER BY id DESC"
            
            with get_connection() as cnx:
                rows = cnx.execute(query, params).fetchall()

            for row in rows:
                yaos_str = f"{row['初爻']}{row['二爻']}{row['三爻']}{row['四爻']}{row['五爻']}{row['上爻']}"
                results.append({
                    'id': row['id'],
                    'time': row['时间'],
                    'user': row['用户'],
                    'subject': row['标的'],
                    'mode': row['起卦方式'],
                    'month_gz': f"{row['月干']}{row['月支']}",
                    'day_gz': f"{row['日干']}{row['日支']}",
                    'yaos': yaos_str
                })
        except Exception as e:
            print(f"Error querying history: {e}")

    return render_template('liuyao_history.html', 
                         results=results,
                         available_years=available_years,
                         current_year=year_table,
                         search_date=search_date,
                         search_subject=search_subject,
                         search_user=search_user)

def _render_liuyao_record(year_table, record_id):
    if not re.match(r'^\d{4}$', year_table):
        return "Invalid year", 400
        
    table_name = f"{year_table}年"
    
    try:
        with get_connection() as cnx:
            query = f"SELECT * FROM {quote_identifier(table_name)} WHERE id = ?"
            row = cnx.execute(query, (record_id,)).fetchone()
        
        if not row:
            return "Record not found", 404
            
        time_str = row['时间']
        try:
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                nums = re.findall(r'\d+', time_str)
                if len(nums) == 5:
                    dt = datetime(int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3]), int(nums[4]))
                elif len(nums) == 4:
                    dt = datetime(int(year_table), int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3]))
                else:
                    print(f"Warning: Could not parse date '{time_str}', using current time.")
                    dt = datetime.now()
            except Exception as e:
                print(f"Error parsing date '{time_str}': {e}")
                dt = datetime.now()
        
        ygua = [
            str(row['初爻']),
            str(row['二爻']),
            str(row['三爻']),
            str(row['四爻']),
            str(row['五爻']),
            str(row['上爻'])
        ]
        
        gz_month = f"{row['月干']}{row['月支']}"
        gz_day = f"{row['日干']}{row['日支']}"
        
        wapp = create_wapp(
            subject=row['标的'],
            ygua=ygua,
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=dt.hour,
            minute=dt.minute,
            gz_month=gz_month,
            gz_day=gz_day
        )
        
        result_data = wapp.get_paipan_data()
        
        ganzhi_info = {
            'month_gan': row['月干'],
            'month_zhi': row['月支'],
            'day_gan': row['日干'],
            'day_zhi': row['日支']
        }
        
        mapping_rev = {'1': '少阳', '2': '少阴', '3': '老阳', '4': '老阴'}
        yao_list_bottom_to_top = [mapping_rev.get(code, '少阳') for code in ygua]
        yao_list = list(reversed(yao_list_bottom_to_top))

        history_results, available_years = _query_liuyao_history(year_table)
        
        return render_template('liuyao.html',
            result_data=result_data,
            subject=row['标的'],
            user=row['用户'],
            remarks=dict(row).get('备注', ''),
            year_table=year_table,
            record_id=record_id,
            date_str=dt.strftime('%Y-%m-%d'),
            hour=dt.hour,
            minute=dt.minute,
            ganzhi_info=ganzhi_info,
            ygua_codes=ygua,
            yao_list=yao_list,
            month_gan=row['月干'],
            month_zhi=row['月支'],
            day_gan=row['日干'],
            day_zhi=row['日支'],
            input_mode='manual',
            is_history=True,
            history_results=history_results,
            available_years=available_years,
            h_year=year_table,
            h_subject='',
            h_user='',
            h_date=''
        )

    except Exception as e:
        print(f"Error viewing history: {e}")
        return f"Error: {e}", 500


@app.route('/history/view/<year_table>/<int:record_id>')
def view_history(year_table, record_id):
    return _render_liuyao_record(year_table, record_id)

@app.route('/update_remarks', methods=['POST'])
def update_remarks():
    try:
        data = request.json
        year_table = data.get('year_table')
        record_id = data.get('record_id')
        remarks = data.get('remarks')
        
        if not year_table or not record_id:
             return jsonify({"status": "error", "message": "Missing parameters"}), 400
        if not re.match(r'^\d{4}$', str(year_table)):
            return jsonify({"status": "error", "message": "Invalid year"}), 400

        table_name = f"{year_table}年"
        
        with get_connection() as cnx:
            update_sql = f"UPDATE {quote_identifier(table_name)} SET 备注 = ? WHERE id = ?"
            cnx.execute(update_sql, (remarks, record_id))
            cnx.commit()
        
        return jsonify({"status": "success", "message": "备注更新成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/history/delete', methods=['POST'])
def delete_history():
    try:
        data = request.json
        year_table = data.get('year_table')
        record_id = data.get('record_id')

        if not year_table or not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        if not re.match(r'^\d{4}$', str(year_table)):
            return jsonify({"status": "error", "message": "Invalid year"}), 400

        table_name = f"{year_table}年"
        with get_connection() as cnx:
            delete_sql = f"DELETE FROM {quote_identifier(table_name)} WHERE id = ?"
            cursor = cnx.execute(delete_sql, (record_id,))
            cnx.commit()

        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404

        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/bazi', methods=['GET', 'POST'])
def bazi_index():
    """八字已并入命理页，重定向到 /mingli?tab=bazi 以保持旧链接可用。"""
    return redirect(url_for('mingli_index', tab='bazi'))
@app.route("/bazi/save", methods=["POST"])
def bazi_save():
    try:
        data = request.json
        date_str_full = data.get("date_str")
        pillars = data.get("pillars") or []
        if len(pillars) != 4:
            return jsonify({"status": "error", "message": "四柱数据不完整"}), 400
        subject = data.get("subject", "")
        gender = data.get("gender", "男")
        remarks = data.get("remarks", "")
        tags = data.get("tags", "") or ""
        solar_minutes = int(data.get("solar_minutes") or 0)
        hour_unknown = bool(data.get("hour_unknown"))
        _insert_bazi_record(subject, gender, date_str_full, pillars, remarks,
                            tags, solar_minutes, hour_unknown)
        return jsonify({"status": "success", "message": "保存成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/bazi/history")
def bazi_history():
    search_year = request.args.get("year", "")
    search_date = request.args.get("search_date", "")
    search_name = request.args.get("search_name", "")

    available_years = []
    results = []
    with get_connection() as cnx:
        ensure_bazi_table(cnx)
        year_rows = cnx.execute(
            "SELECT DISTINCT substr(时间, 1, 4) AS y FROM bazi_records "
            "WHERE 时间 IS NOT NULL AND length(时间) >= 4 ORDER BY y DESC"
        ).fetchall()
        available_years = [r["y"] for r in year_rows]

        query = "SELECT * FROM bazi_records WHERE 1=1"
        params = []
        if search_year:
            query += " AND substr(时间, 1, 4) = ?"
            params.append(search_year)
        if search_date:
            query += " AND 时间 LIKE ?"
            params.append(f"{search_date}%")
        if search_name:
            query += " AND 姓名 LIKE ?"
            params.append(f"%{search_name}%")
        query += " ORDER BY id DESC"
        rows = cnx.execute(query, params).fetchall()

    for row in rows:
        pillars = " ".join(
            f"{row[c1]}{row[c2]}"
            for c1, c2 in [("年干", "年支"), ("月干", "月支"), ("日干", "日支"), ("时干", "时支")]
        )
        results.append({
            "id": row["id"],
            "time": row["时间"],
            "gender": row["性别"],
            "name": row["姓名"],
            "pillars": pillars,
            "remarks": row["备注"] or "",
        })

    return render_template(
        "bazi_history.html",
        results=results,
        available_years=available_years,
        current_year=search_year,
        search_date=search_date,
        search_name=search_name,
    )


def _render_bazi_record(record_id, open_archive=False, edit_record=False):
    try:
        with get_connection() as cnx:
            ensure_bazi_table(cnx)
            row = cnx.execute(
                "SELECT * FROM bazi_records WHERE id = ?", (record_id,)
            ).fetchone()
        if not row:
            return "Record not found", 404

        dt = datetime.strptime(row["时间"], "%Y-%m-%d %H:%M")
        hour_unknown = (row["时柱未知"] or "") == "是"
        solar_minutes = int(row["校正分钟"] or 0)
        gz_year = f"{row['年干']}{row['年支']}"
        gz_month = f"{row['月干']}{row['月支']}"
        gz_day = f"{row['日干']}{row['日支']}"
        gz_hour = f"{row['时干']}{row['时支']}" if not hour_unknown else None

        app, bazi_text = perform_bazi(
            row["姓名"], row["性别"],
            dt.year, dt.month, dt.day, dt.hour, dt.minute,
            gz_year=gz_year, gz_month=gz_month, gz_day=gz_day, gz_hour=gz_hour,
            solar_minutes=solar_minutes, hour_unknown=hour_unknown,
        )
        result_data = app.get_data()
        records = get_bazi_records()

        return render_template(
            "bazi.html",
            result_data=result_data,
            bazi_text=bazi_text,
            error="",
            subject=row["姓名"],
            gender=row["性别"],
            tags=row["标签"] or "",
            solar_minutes=solar_minutes,
            hour_unknown=hour_unknown,
            records=records,
            q="",
            date_str=dt.strftime("%Y-%m-%d"),
            hour=dt.hour,
            minute=dt.minute,
            year_gan=row["年干"],
            year_zhi=row["年支"],
            month_gan=row["月干"],
            month_zhi=row["月支"],
            day_gan=row["日干"],
            day_zhi=row["日支"],
            hour_gan=row["时干"],
            hour_zhi=row["时支"],
            is_history=not edit_record,
            record_id=record_id,
            remarks=row["备注"] or "",
            new_record=edit_record,
            edit_record=edit_record,
            edit_id=record_id if edit_record else "",
            open_archive=open_archive,
        )
    except Exception as e:
        print(e)
        return f"Error: {e}", 500


@app.route("/bazi/history/view/<int:record_id>")
def bazi_history_view(record_id):
    return _render_bazi_record(record_id)


@app.route("/bazi/update_remarks", methods=["POST"])
def bazi_update_remarks():
    try:
        data = request.json
        record_id = data.get("record_id")
        remarks = data.get("remarks")
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_bazi_table(cnx)
            cnx.execute(
                "UPDATE bazi_records SET 备注 = ? WHERE id = ?", (remarks, record_id)
            )
            cnx.commit()
        return jsonify({"status": "success", "message": "备注更新成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/bazi/delete", methods=["POST"])
def bazi_delete():
    try:
        data = request.json
        record_id = data.get("record_id")
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_bazi_table(cnx)
            cursor = cnx.execute(
                "DELETE FROM bazi_records WHERE id = ?", (record_id,)
            )
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/save', methods=['POST'])
def save_result():
    try:
        data = request.json
        input_mode = data.get('input_mode')
        date_str_full = data.get('date_str') 
        dt = datetime.strptime(date_str_full, '%Y-%m-%d %H:%M')
        year = dt.year
        
        month_gan = data.get('month_gan')
        month_zhi = data.get('month_zhi')
        day_gan = data.get('day_gan')
        day_zhi = data.get('day_zhi')
        
        yaos = data.get('yaos') 
        
        subject = data.get('subject')
        user = data.get('user')
        remarks = data.get('remarks', '')
        
        with get_connection() as cnx:
            table_name = ensure_year_table(cnx, year)
            insert_sql = f"""
        INSERT INTO {quote_identifier(table_name)} 
        (起卦方式, 时间, 月干, 月支, 日干, 日支, 初爻, 二爻, 三爻, 四爻, 五爻, 上爻, 标的, 用户, 备注)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
            mode_map = {'manual': '指定', 'random': '多随机', 'single': '单随机'}
            values = (
                mode_map.get(input_mode, input_mode),
                dt.strftime('%Y-%m-%d %H:%M'), 
                month_gan, month_zhi, day_gan, day_zhi,
                yaos[0], yaos[1], yaos[2], yaos[3], yaos[4], yaos[5],
                subject, user, remarks
            )
            cnx.execute(insert_sql, values)
            cnx.commit()
        
        return jsonify({"status": "success", "message": "保存成功"})
        
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/liuyao', methods=['GET', 'POST'])
def liuyao():
    # 页面内历史记录：?year=YYYY&id=N 直接加载某条记录
    if request.method == 'GET':
        year_param = request.args.get('year', '')
        id_param = request.args.get('id', '')
        if year_param and id_param:
            try:
                return _render_liuyao_record(year_param, int(id_param))
            except (ValueError, TypeError):
                pass

    result = ""
    result_data = None
    subject = ""
    user = ""
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    hour = now.hour
    minute = now.minute
    yao_list = ['少阳'] * 6
    input_mode = 'manual'
    ygua_codes = []
    ganzhi_info = {}

    if request.method == 'POST':
        try:
            subject = request.form.get('subject', '')
            user = request.form.get('user', '')
            date_str = request.form.get('date')
            hour = int(request.form.get('hour'))
            minute = int(request.form.get('minute'))
            input_mode = request.form.get('input_mode', 'manual')
            
            # Parse date
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            year, month, day = dt.year, dt.month, dt.day

            ygua_codes = []
            
            if input_mode == 'manual':
                input_yaos = []
                for i in range(6):
                    val = request.form.get(f'yao_{i}')
                    input_yaos.append(val)
                
                yao_list = input_yaos
                
                mapping = {'少阳': '1', '少阴': '2', '老阳': '3', '老阴': '4'}
                ygua_codes = [mapping[y] for y in input_yaos]
                ygua_codes = list(reversed(ygua_codes))

            elif input_mode == 'random':
                remainder_map = {0: '4', 1: '1', 2: '2', 3: '3'}
                codes_top_to_bottom = []
                
                for i in range(6):
                    val_str = request.form.get(f'random_val_{i}', '')
                    try:
                        val = int(val_str)
                        if val <= 10:
                            raise ValueError(f"第{6-i}爻的随机数必须大于10")
                        code = remainder_map[val % 4]
                        codes_top_to_bottom.append(code)
                    except ValueError as ve:
                        raise ValueError(f"随机数输入错误: {str(ve)}")
                
                ygua_codes = list(reversed(codes_top_to_bottom))

            elif input_mode == 'single':
                val_str = request.form.get('single_random_val', '').strip()
                if not val_str.isdigit() or len(val_str) != 6:
                    raise ValueError("单随机模式需要输入6位数字")
                
                digits = [int(d) for d in val_str]
                if any(d < 1 or d > 8 for d in digits):
                    raise ValueError("单随机模式每位数字必须在1-8之间")
                
                digits_bottom_to_top = list(reversed(digits))
                
                remainder_map = {0: '4', 1: '1', 2: '2', 3: '3'}
                ygua_codes = []
                for d in digits_bottom_to_top:
                    ygua_codes.append(remainder_map[d % 4])

            def combine_gz(gan, zhi):
                if gan and zhi: return gan + zhi
                return None

            gz_year_val = combine_gz(request.form.get('year_gan'), request.form.get('year_zhi'))
            gz_month_val = combine_gz(request.form.get('month_gan'), request.form.get('month_zhi'))
            gz_day_val = combine_gz(request.form.get('day_gan'), request.form.get('day_zhi'))
            gz_hour_val = combine_gz(request.form.get('hour_gan'), request.form.get('hour_zhi'))

            wapp, output = perform_divination(subject, ygua_codes, year, month, day, hour, minute,
                                              gz_year=gz_year_val, gz_month=gz_month_val, 
                                              gz_day=gz_day_val, gz_hour=gz_hour_val)
            result = output
            result_data = wapp.get_paipan_data()
            
            if hasattr(wapp, 'wanzu'):
                mgz = wapp.wanzu[1]
                dgz = wapp.wanzu[2]
                ganzhi_info = {
                    'month_gan': mgz[0],
                    'month_zhi': mgz[1],
                    'day_gan': dgz[0],
                    'day_zhi': dgz[1]
                }
            
        except Exception as e:
            result = f"发生错误: {str(e)}"

    h_year = request.args.get('h_year', datetime.now().strftime('%Y'))
    h_subject = request.args.get('h_subject', '')
    h_user = request.args.get('h_user', '')
    h_date = request.args.get('h_date', '')
    history_results, available_years = _query_liuyao_history(h_year, h_date, h_subject, h_user)

    return render_template('liuyao.html', 
                           result=result, 
                           result_data=result_data,
                           subject=subject, 
                           user=user,
                           date_str=date_str, 
                           hour=hour, 
                           minute=minute,
                           yao_list=yao_list,
                           input_mode=input_mode,
                           ygua_codes=ygua_codes,
                           ganzhi_info=ganzhi_info,
                           is_history=False,
                           history_results=history_results,
                           available_years=available_years,
                           h_year=h_year,
                           h_subject=h_subject,
                           h_user=h_user,
                           h_date=h_date,
                           year_gan=request.form.get('year_gan', ''),
                           year_zhi=request.form.get('year_zhi', ''),
                           month_gan=request.form.get('month_gan', ''),
                           month_zhi=request.form.get('month_zhi', ''),
                           day_gan=request.form.get('day_gan', ''),
                           day_zhi=request.form.get('day_zhi', ''),
                           hour_gan=request.form.get('hour_gan', ''),
                           hour_zhi=request.form.get('hour_zhi', ''))


# --------------------------------------------------------------------------
# 奇门遁甲
# --------------------------------------------------------------------------

QIMEN_METHODS = ('时家', '日家', '月家', '年家')
QIMEN_PURPOSES = ('综合', '事业', '财运', '婚姻', '健康', '学业')

# 起局精度选项：真太阳时、晚子时、年柱分界、定局法、日家置闰
QIMEN_OPTION_DEFAULTS = {
    'longitude': '',
    'eot': '1',
    'late_zi': '1',
    'ding_ju': '拆补',
    'ri_run': '延续',
    'year_rule': '立春',
}


def _parse_qimen_options(source):
    """从 GET/POST 参数解析起局选项，前后端口径一致。"""
    opts = dict(QIMEN_OPTION_DEFAULTS)
    lon = source.get('longitude')
    try:
        opts['longitude'] = float(lon) if lon not in (None, '') else ''
    except (TypeError, ValueError):
        opts['longitude'] = ''
    for key in ('eot', 'late_zi'):
        val = source.get(key)
        if val in ('1', 'on', 'true', 'True'):
            opts[key] = '1'
        elif val in ('0', 'off', 'false', 'False'):
            opts[key] = '0'
    for key, allowed in (
        ('ding_ju', qimen_lib.constants.DING_JU_METHODS),
        ('ri_run', qimen_lib.constants.RI_RUN_MODES),
        ('year_rule', qimen_lib.constants.YEAR_RULES),
    ):
        if source.get(key) in allowed:
            opts[key] = source.get(key)
    return opts


def _qimen_calc_options(opts):
    """把 URL 选项转换成 calculate() 需要的类型。"""
    opts = opts or QIMEN_OPTION_DEFAULTS
    return {
        'longitude': opts.get('longitude') if opts.get('longitude') != '' else None,
        'eot': opts.get('eot', '1') == '1',
        'late_zi': opts.get('late_zi', '1') == '1',
        'ding_ju': opts.get('ding_ju', '拆补'),
        'ri_run': opts.get('ri_run', '延续'),
        'year_rule': opts.get('year_rule', '立春'),
    }


def _build_qimen_pan(date, method='时家', purpose='综合', location='默认位置',
                     type_param='四柱', options=None):
    """计算奇门盘并补齐模板所需的缺省字段。"""
    pan = qimen_lib.calculate(date, {
        'type': type_param,
        'method': method,
        'purpose': purpose,
        'location': location,
        **_qimen_calc_options(options),
    })
    pan.setdefault('jiuGongAnalysis', {})
    pan.setdefault('anGan', {})
    pan.setdefault('geJuLegend', [])
    pan.setdefault('markSummary', '')
    pan.setdefault('timeInfo', {})
    # 补齐原始日期/时间，便于前端保存记录时回填表单
    basic_info = pan.setdefault('basicInfo', {})
    basic_info.setdefault('dateRaw', date.strftime('%Y-%m-%d'))
    basic_info.setdefault('timeRaw', date.strftime('%H:%M'))
    for i in range(1, 10):
        gong = str(i)
        pan['jiuGongAnalysis'].setdefault(gong, {
            'direction': '',
            'gongName': '',
            'jiXiong': 'ping',
        })
        pan['jiuGongAnalysis'][gong].setdefault('markKeys', [])
        pan['jiuGongAnalysis'][gong].setdefault('marks', [])
        pan['jiuGongAnalysis'][gong].setdefault('anGan', '')
        pan['jiuGongAnalysis'][gong].setdefault('geJuText', '')
        pan['jiuGongAnalysis'][gong].setdefault('yiMa', False)
    return pan


def _qimen_constants():
    """奇门模板需要用到的常量表。"""
    return {
        'JIU_GONG': qimen_lib.JIU_GONG,
        'JIU_XING': qimen_lib.JIU_XING,
        'BA_MEN': qimen_lib.BA_MEN,
        'BA_SHEN': qimen_lib.BA_SHEN,
    }


def _render_qimen_pan(date, method='时家', purpose='综合', location='默认位置',
                      type_param='四柱', options=None, **extra):
    """渲染奇门排盘页面。"""
    options = options or dict(QIMEN_OPTION_DEFAULTS)
    pan = _build_qimen_pan(date, method, purpose, location, type_param, options)
    ctx = {
        'qimen': pan,
        'records': get_qimen_records(),
        'current_method': method,
        'current_purpose': purpose,
        'current_location': location,
        'qimen_options': options,
        'record_id': None,
        'remarks': '',
        'tags': '',
        'subject': '',
        'question': '',
        'is_history': False,
    }
    ctx.update(extra)
    ctx.update(_qimen_constants())
    return render_template('qimen.html', **ctx)


def get_qimen_records(q=""):
    """查询奇门记录（供页面内记录切换使用）。"""
    records = []
    with get_connection() as cnx:
        ensure_qimen_table(cnx)
        query = "SELECT * FROM qimen_records WHERE 1=1"
        params = []
        if q:
            query += " AND (问事 LIKE ? OR 标的 LIKE ? OR 标签 LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        query += " ORDER BY id DESC LIMIT 60"
        rows = cnx.execute(query, params).fetchall()
    for row in rows:
        records.append({
            "id": row["id"],
            "time": row["时间"],
            "method": row["方法"],
            "subject": row["标的"] or "",
            "question": row["问事"] or "",
            "location": row["地点"] or "",
            "purpose": row["目的"] or "",
            "ju_shu": row["局数"] or "",
            "tags": row["标签"] or "",
            "remarks": row["备注"] or "",
        })
    return records


def _insert_qimen_record(date_str, method, subject, location, purpose, ju_shu,
                         remarks="", tags="", qu_fa="", question=""):
    """写入一条奇门记录，返回新记录 id；取法（起局选项）以 JSON 保存。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    with get_connection() as cnx:
        ensure_qimen_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO qimen_records
            (时间, 方法, 标的, 问事, 地点, 目的, 局数, 备注, 标签, 取法)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dt.strftime("%Y-%m-%d %H:%M"), method, subject, question,
                location, purpose, ju_shu, remarks, tags, qu_fa,
            ),
        )
        cnx.commit()
        return cursor.lastrowid


def _render_qimen_record(record_id):
    """渲染某条奇门历史记录（按其保存时的取法重算）。"""
    with get_connection() as cnx:
        ensure_qimen_table(cnx)
        row = cnx.execute(
            "SELECT * FROM qimen_records WHERE id = ?", (record_id,)
        ).fetchone()
    if not row:
        return "Record not found", 404

    try:
        saved = json.loads(row["取法"] or '{}')
        options = {**QIMEN_OPTION_DEFAULTS, **saved}
    except (ValueError, TypeError):
        options = dict(QIMEN_OPTION_DEFAULTS)

    dt = datetime.strptime(row["时间"], "%Y-%m-%d %H:%M")
    pan = _build_qimen_pan(
        dt,
        method=row["方法"] or '时家',
        purpose=row["目的"] or '综合',
        location=row["地点"] or '默认位置',
        options=options,
    )
    return render_template(
        'qimen.html',
        qimen=pan,
        records=get_qimen_records(),
        current_method=row["方法"] or '时家',
        current_purpose=row["目的"] or '综合',
        current_location=row["地点"] or '默认位置',
        qimen_options=options,
        record_id=record_id,
        remarks=row["备注"] or "",
        tags=row["标签"] or "",
        subject=row["标的"] or "",
        question=row["问事"] or "",
        is_history=True,
        **_qimen_constants(),
    )


@app.route('/qimen', methods=['GET', 'POST'])
def qimen_index():
    """奇门排盘主页：GET 渲染（含 ?record_id=N 载入历史），POST 保存并跳转。"""
    if request.method == 'GET':
        record_id = request.args.get('record_id')
        if record_id:
            try:
                return _render_qimen_record(int(record_id))
            except (ValueError, TypeError):
                pass

    values = request.values
    options = _parse_qimen_options(values)
    method = values.get('method', '时家')
    purpose = values.get('purpose', '综合')
    location = values.get('location') or '默认位置'
    date_str = values.get('date')
    time_str = values.get('time')

    if method not in QIMEN_METHODS:
        method = '时家'
    if purpose not in QIMEN_PURPOSES:
        purpose = '综合'

    if date_str and time_str:
        try:
            date = datetime.fromisoformat(f'{date_str}T{time_str}')
        except ValueError:
            date = datetime.now()
    else:
        date = datetime.now()

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        question = request.form.get('question', '').strip()
        remarks = request.form.get('remarks', '')
        tags = request.form.get('tags', '').strip()
        error = ""
        try:
            if not question:
                # 与六爻「占事主题」一致：问事为必填，服务端再兜一层校验
                error = "请填写问事（所问何事）"
            else:
                dt = datetime.strptime(
                    f"{request.form.get('date')} {request.form.get('time')}",
                    "%Y-%m-%d %H:%M",
                )
                pan = _build_qimen_pan(dt, method, purpose, location,
                                       options=options)
                record_id = _insert_qimen_record(
                    dt.strftime("%Y-%m-%d %H:%M"), method, subject, location,
                    purpose, (pan.get('juShu') or {}).get('fullName', ''),
                    remarks=remarks, tags=tags,
                    qu_fa=json.dumps(options, ensure_ascii=False),
                    question=question,
                )
                return redirect(url_for('qimen_index', record_id=record_id))
        except Exception as e:
            print(e)
            error = f"保存失败: {e}"

        return _render_qimen_pan(
            date, method, purpose, location, options=options,
            remarks=remarks, tags=tags, subject=subject, question=question,
            error=error,
        )

    return _render_qimen_pan(date, method, purpose, location, options=options)


@app.route('/qimen/custom')
def qimen_custom():
    """自定义排盘（表单提交入口）。"""
    type_param = request.args.get('type', '四柱')
    method = request.args.get('method', '时家')
    purpose = request.args.get('purpose', '综合')
    location = request.args.get('location') or '默认位置'
    date_str = request.args.get('date')
    time_str = request.args.get('time')

    if date_str and time_str:
        try:
            date = datetime.fromisoformat(f'{date_str}T{time_str}')
        except ValueError:
            return '无效的日期时间', 400
    else:
        date = datetime.now()

    if method not in QIMEN_METHODS:
        method = '时家'
    if purpose not in QIMEN_PURPOSES:
        purpose = '综合'

    options = _parse_qimen_options(request.args)
    try:
        return _render_qimen_pan(date, method, purpose, location,
                                 type_param, options)
    except Exception as e:
        print(f'自定义排盘错误: {e}')
        return f'排盘错误: {e}', 500


@app.route('/qimen/api')
def qimen_api():
    """奇门排盘 JSON 接口（供前端切换时间/方法时局部刷新）。"""
    type_param = request.args.get('type', '四柱')
    method = request.args.get('method', '时家')
    purpose = request.args.get('purpose', '综合')
    location = request.args.get('location') or '默认位置'
    date_str = request.args.get('date')
    time_str = request.args.get('time')

    if date_str and time_str:
        try:
            date = datetime.fromisoformat(f'{date_str}T{time_str}')
        except ValueError:
            return jsonify({'error': True, 'message': '无效的日期时间'}), 400
    else:
        date = datetime.now()

    if method not in QIMEN_METHODS:
        method = '时家'
    if purpose not in QIMEN_PURPOSES:
        purpose = '综合'

    options = _parse_qimen_options(request.args)
    try:
        return jsonify(_build_qimen_pan(date, method, purpose, location,
                                        type_param, options))
    except Exception as e:
        print(f'奇门 API 错误: {e}')
        return jsonify({'error': True, 'message': str(e)}), 500


@app.route('/qimen/update_remarks', methods=['POST'])
def qimen_update_remarks():
    """更新历史记录的备注；若请求带 question，则一并更新问事。"""
    try:
        data = request.json or {}
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        sets, params = [], []
        if 'remarks' in data:
            sets.append('备注 = ?')
            params.append(data.get('remarks') or '')
        if 'question' in data:
            sets.append('问事 = ?')
            # 旧记录可能没有问事，允许留空以便只改备注
            params.append((data.get('question') or '').strip())
        if not sets:
            return jsonify({"status": "error", "message": "没有可更新的字段"}), 400
        params.append(record_id)
        with get_connection() as cnx:
            ensure_qimen_table(cnx)
            cnx.execute(
                f"UPDATE qimen_records SET {', '.join(sets)} WHERE id = ?", params
            )
            cnx.commit()
        return jsonify({"status": "success", "message": "记录已更新"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/qimen/delete', methods=['POST'])
def qimen_delete():
    try:
        data = request.json
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_qimen_table(cnx)
            cursor = cnx.execute("DELETE FROM qimen_records WHERE id = ?", (record_id,))
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# 小六壬
# 两派起课不同：江氏用日时（大安起初一、日宫起子时），道传用月日时（三才三宫）。
# 盘面完全由「时间 + 流派」决定，记录只存这两项，载入时重算。
# ---------------------------------------------------------------------------

XLR_GRID = ['留连', '速喜', '赤口', '大安', '空亡', '小吉']  # 掌上方位：上节一行、下节一行


def parse_xlr_numbers(text):
    """从「7 15 9」「7,15,9」「7、15、9」之类输入中取出报数。"""
    return [int(x) for x in re.findall(r'\d+', text or '')]


def get_xiaoliuren_records(limit=60):
    """查询小六壬记录（供页面内记录切换使用）。"""
    records = []
    with get_connection() as cnx:
        ensure_xiaoliuren_table(cnx)
        rows = cnx.execute(
            "SELECT * FROM xiaoliuren_records ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    for row in rows:
        school = row["流派"] or "jiang"
        method = row["起课方式"] or "time"
        records.append({
            "id": row["id"],
            "time": row["时间"],
            "school": school,
            "school_label": XLR_SCHOOLS.get(school, "江氏"),
            "method": method,
            "method_label": XLR_METHODS.get(school, {}).get(method, "时间起课"),
            "numbers": row["报数"] or "",
            "subject": row["标的"] or "",
            "lunar": row["农历"] or "",
            "shichen": row["时辰"] or "",
            "summary": row["摘要"] or "",
            "tags": row["标签"] or "",
            "remarks": row["备注"] or "",
        })
    return records


def _insert_xiaoliuren_record(dt_str, school, subject, lunar, shichen, summary,
                              remarks="", tags="", method="time", numbers=""):
    with get_connection() as cnx:
        ensure_xiaoliuren_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO xiaoliuren_records
            (时间, 流派, 起课方式, 报数, 标的, 备注, 标签, 农历, 时辰, 摘要)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dt_str, school, method, numbers, subject, remarks, tags,
             lunar, shichen, summary),
        )
        cnx.commit()
        return cursor.lastrowid


def _render_xiaoliuren(dt, school, record_id=None, subject="", remarks="", tags="",
                       error="", method="time", numbers=None):
    numbers = list(numbers or [])
    try:
        pan = xlr_calculate(school, dt, method=method, numbers=numbers)
    except ValueError as e:
        # 报数不足或非法：退回时间起课，保留用户输入以便修正
        pan = xlr_calculate(school, dt)
        method = 'time'
        error = error or str(e)

    return render_template(
        'xiaoliuren.html',
        xlr=pan,
        school=school,
        school_options=XLR_SCHOOLS,
        method=pan['method'],
        method_options=XLR_METHODS[school],
        need_count=XLR_NUM_COUNT[school],
        numbers_str=' '.join(str(n) for n in numbers),
        date_value=dt.strftime('%Y-%m-%d'),
        time_value=dt.strftime('%H:%M'),
        records=get_xiaoliuren_records(),
        record_id=record_id,
        subject=subject,
        remarks=remarks,
        tags=tags,
        grid_order=XLR_GRID,
        palace_desc=xlr_data.PALACE_DESC,
        error=error,
    )


@app.route('/xiaoliuren', methods=['GET', 'POST'])
def xiaoliuren_index():
    """小六壬排盘：GET 起课（可带 ?record_id=N 载入），POST 保存并跳转。"""
    school = request.args.get('school', 'jiang')
    if school not in XLR_SCHOOLS:
        school = 'jiang'

    if request.method == 'GET':
        record_id = request.args.get('record_id')
        if record_id:
            try:
                rid = int(record_id)
                with get_connection() as cnx:
                    ensure_xiaoliuren_table(cnx)
                    row = cnx.execute(
                        "SELECT * FROM xiaoliuren_records WHERE id = ?", (rid,)
                    ).fetchone()
                if row:
                    rec_school = row["流派"] if row["流派"] in XLR_SCHOOLS else 'jiang'
                    rec_method = row["起课方式"] or "time"
                    if rec_method not in XLR_METHODS[rec_school]:
                        rec_method = "time"
                    dt = datetime.strptime(row["时间"], "%Y-%m-%d %H:%M")
                    return _render_xiaoliuren(
                        dt, rec_school, record_id=rid,
                        subject=row["标的"] or "", remarks=row["备注"] or "",
                        tags=row["标签"] or "",
                        method=rec_method,
                        numbers=parse_xlr_numbers(row["报数"]),
                    )
            except (ValueError, TypeError):
                pass

    method = request.values.get('method', 'time')
    if method not in XLR_METHODS[school]:
        method = 'time'
    numbers = parse_xlr_numbers(request.values.get('numbers'))

    date_str = request.values.get('date')
    time_str = request.values.get('time')
    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            dt = datetime.now()
    else:
        dt = datetime.now()

    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        remarks = request.form.get('remarks', '')
        tags = request.form.get('tags', '').strip()
        try:
            pan = xlr_calculate(school, dt, method=method, numbers=numbers)
            record_id = _insert_xiaoliuren_record(
                dt.strftime("%Y-%m-%d %H:%M"), school, subject,
                pan['lunar_str'], pan['shichen'], xlr_summary(pan),
                remarks=remarks, tags=tags,
                method=pan['method'],
                numbers=' '.join(str(n) for n in pan['numbers']),
            )
            return redirect(url_for('xiaoliuren_index', record_id=record_id))
        except Exception as e:
            print(e)
            return _render_xiaoliuren(dt, school, subject=subject, remarks=remarks,
                                      tags=tags, error=f"保存失败: {e}",
                                      method=method, numbers=numbers)

    return _render_xiaoliuren(dt, school, method=method, numbers=numbers)


@app.route('/xiaoliuren/delete', methods=['POST'])
def xiaoliuren_delete():
    try:
        data = request.json
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_xiaoliuren_table(cnx)
            cursor = cnx.execute("DELETE FROM xiaoliuren_records WHERE id = ?", (record_id,))
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# 梅花易数
# 盘面完全由「起卦时刻 + 起卦方式 + 起卦参数」决定，记录只存输入，载入时重算。
# 与奇门一致：保存记录必须填写「问事」。
# ---------------------------------------------------------------------------

MH_PARAM_DEFAULTS = {
    'method': 'time',
    'numbers': [],
    'manual': {'upper': '乾', 'lower': '坤', 'dong': 1},
    'year_rule': '正月',
}


def parse_mh_numbers(text):
    """从「37 82」「37,82」这类输入中取出报数（取前两个）。"""
    return [int(x) for x in re.findall(r'\d+', text or '')][:2]


def _mh_params_from(values):
    """统一解析主页／API／保存表单中的起卦方式参数。"""
    method = values.get('method', 'time')
    if method not in MH_METHODS:
        method = 'time'
    year_rule = values.get('year_rule', '正月')
    if year_rule not in MH_YEAR_RULES:
        year_rule = '正月'
    try:
        dong = int(values.get('dong', 1))
    except (TypeError, ValueError):
        dong = 1
    upper = values.get('upper', '乾')
    lower = values.get('lower', '坤')
    return {
        'method': method,
        'numbers': parse_mh_numbers(values.get('numbers')),
        'manual': {
            'upper': upper if upper in MH_TRIGRAMS else '乾',
            'lower': lower if lower in MH_TRIGRAMS else '坤',
            'dong': min(max(dong, 1), 6),
        },
        'year_rule': year_rule,
    }


def _mh_params_saved(params):
    """规范化落库／回放的参数，兼容旧记录的空串或畸形字段。"""
    params = params if isinstance(params, dict) else {}
    manual = params.get('manual') if isinstance(params.get('manual'), dict) else {}
    numbers = params.get('numbers') if isinstance(params.get('numbers'), list) else []
    return {
        'method': params.get('method') if params.get('method') in MH_METHODS else 'time',
        'numbers': [int(n) for n in numbers[:2]],
        'manual': {
            'upper': manual.get('upper') if manual.get('upper') in MH_TRIGRAMS else '乾',
            'lower': manual.get('lower') if manual.get('lower') in MH_TRIGRAMS else '坤',
            'dong': min(max(int(manual.get('dong') or 1), 1), 6),
        },
        'year_rule': params.get('year_rule') if params.get('year_rule') in MH_YEAR_RULES else '正月',
    }


def get_meihua_records(limit=60):
    """查询梅花易数记录（供页面内记录切换使用）。"""
    records = []
    with get_connection() as cnx:
        ensure_meihua_table(cnx)
        rows = cnx.execute(
            "SELECT * FROM meihua_records ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    for row in rows:
        method = row["起卦方式"] or "time"
        records.append({
            "id": row["id"],
            "time": row["时间"],
            "method": method,
            "method_label": MH_METHODS.get(method, "时间起卦"),
            "question": row["问事"] or "",
            "subject": row["标的"] or "",
            "ben": row["本卦"] or "",
            "summary": row["摘要"] or "",
            "remarks": row["备注"] or "",
            "tags": row["标签"] or "",
        })
    return records


def _insert_meihua_record(dt_str, params, question, subject, ben, summary,
                          remarks="", tags=""):
    """写入一条梅花易数记录，返回新记录 id。"""
    params = _mh_params_saved(params)
    with get_connection() as cnx:
        ensure_meihua_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO meihua_records
            (时间, 起卦方式, 参数, 问事, 标的, 备注, 标签, 本卦, 摘要)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dt_str, params['method'], json.dumps(params, ensure_ascii=False),
             question, subject, remarks, tags, ben, summary),
        )
        cnx.commit()
        return cursor.lastrowid


def _render_meihua(dt, params, record_id=None, question="", subject="",
                   remarks="", tags="", error=""):
    """渲染梅花易数页面；参数非法时退回时间起卦并保留提示。"""
    params = _mh_params_saved(params)
    try:
        pan = mh_calculate(
            dt, method=params['method'], numbers=params['numbers'],
            manual=params['manual'], year_rule=params['year_rule'],
        )
    except ValueError as e:
        params = _mh_params_saved({**params, 'method': 'time'})
        pan = mh_calculate(dt, year_rule=params['year_rule'])
        error = error or str(e)
    except (TypeError, KeyError) as e:
        params = _mh_params_saved({})
        pan = mh_calculate(dt)
        error = error or f'参数有误，已按时间起卦：{e}'

    return render_template(
        'meihua.html',
        pan=pan,
        params=params,
        method_options=MH_METHODS,
        year_rules=MH_YEAR_RULES,
        trigrams=MH_TRIGRAMS,
        numbers_str=' '.join(str(n) for n in params['numbers']),
        date_value=dt.strftime('%Y-%m-%d'),
        time_value=dt.strftime('%H:%M'),
        records=get_meihua_records(),
        record_id=record_id,
        question=question,
        subject=subject,
        remarks=remarks,
        tags=tags,
        error=error,
        summary=mh_summary(pan),
    )


@app.route('/meihua', methods=['GET', 'POST'])
def meihua_index():
    """梅花易数排盘：GET 起卦（可带 ?record_id=N 载入历史），POST 保存。"""
    if request.method == 'GET':
        record_id = request.args.get('record_id')
        if record_id:
            try:
                rid = int(record_id)
                with get_connection() as cnx:
                    ensure_meihua_table(cnx)
                    row = cnx.execute(
                        "SELECT * FROM meihua_records WHERE id = ?", (rid,)
                    ).fetchone()
                if row:
                    try:
                        saved = json.loads(row["参数"] or '{}')
                    except (ValueError, TypeError):
                        saved = {}
                    dt = datetime.strptime(row["时间"], "%Y-%m-%d %H:%M")
                    return _render_meihua(
                        dt, saved, record_id=rid,
                        question=row["问事"] or "", subject=row["标的"] or "",
                        remarks=row["备注"] or "", tags=row["标签"] or "",
                    )
            except (ValueError, TypeError):
                pass

    values = request.values
    params = _mh_params_from(values)
    date_str, time_str = values.get('date'), values.get('time')
    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            dt = datetime.now()
    else:
        dt = datetime.now()

    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        subject = request.form.get('subject', '').strip()
        remarks = request.form.get('remarks', '')
        tags = request.form.get('tags', '').strip()
        error = ""
        try:
            if not question:
                error = "请填写问事（所问何事）"
            else:
                pan = mh_calculate(
                    dt, method=params['method'], numbers=params['numbers'],
                    manual=params['manual'], year_rule=params['year_rule'],
                )
                record_id = _insert_meihua_record(
                    dt.strftime("%Y-%m-%d %H:%M"), params, question, subject,
                    pan['ben']['name'], mh_summary(pan),
                    remarks=remarks, tags=tags,
                )
                return redirect(url_for('meihua_index', record_id=record_id))
        except Exception as e:
            print(e)
            error = f"保存失败: {e}"

        return _render_meihua(
            dt, params, question=question, subject=subject,
            remarks=remarks, tags=tags, error=error,
        )

    return _render_meihua(dt, params)


@app.route('/meihua/api')
def meihua_api():
    """梅花易数 JSON 接口（供校验与后续局部刷新使用）。"""
    values = request.args
    params = _mh_params_from(values)
    date_str, time_str = values.get('date'), values.get('time')
    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            return jsonify({'error': True, 'message': '无效的日期时间'}), 400
    else:
        dt = datetime.now()
    try:
        return jsonify(mh_calculate(
            dt, method=params['method'], numbers=params['numbers'],
            manual=params['manual'], year_rule=params['year_rule'],
        ))
    except ValueError as e:
        return jsonify({'error': True, 'message': str(e)}), 400
    except Exception as e:
        print(f'梅花易数 API 错误: {e}')
        return jsonify({'error': True, 'message': str(e)}), 500


@app.route('/meihua/delete', methods=['POST'])
def meihua_delete():
    try:
        data = request.json or {}
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_meihua_table(cnx)
            cursor = cnx.execute("DELETE FROM meihua_records WHERE id = ?", (record_id,))
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# 大六壬
# 课式完全由「起课时刻 + 起课方式 + 手动参数 + 流派选项」决定，记录只存输入，
# 载入历史时按保存参数重算。与奇门／梅花一致：保存须填「问事」。
# ---------------------------------------------------------------------------


def _dlr_params_from(values):
    """统一解析主页／API／保存表单中的起课参数。"""
    return dlr_normalize_options({
        'method': values.get('method', 'time'),
        'manual': {
            'day_gan': values.get('day_gan', '甲'),
            'day_zhi': values.get('day_zhi', '子'),
            'shichen': values.get('shichen', '子'),
            'yuejiang': values.get('yuejiang', '亥'),
        },
        'yuejiang_rule': values.get('yuejiang_rule', '中气'),
        'noble_rule': values.get('noble_rule', '通行'),
        'shehai_rule': values.get('shehai_rule', '计害'),
        'longitude': values.get('longitude', ''),
        'eot': values.get('eot', '1'),
        'late_zi': values.get('late_zi', '1'),
    })


def get_daliuren_records(q="", limit=60):
    """查询大六壬记录；支持按问事、标的、课体、三传、标签搜索。"""
    query = "SELECT * FROM daliuren_records"
    params = []
    if q:
        query += (" WHERE 问事 LIKE ? OR 标的 LIKE ? OR 课体 LIKE ? "
                  "OR 三传 LIKE ? OR 标签 LIKE ?")
        params = [f"%{q}%"] * 5
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_connection() as cnx:
        ensure_daliuren_table(cnx)
        rows = cnx.execute(query, params).fetchall()
    return [{
        "id": row["id"],
        "time": row["时间"],
        "method": row["起课方式"] or "time",
        "method_label": DLR_METHODS.get(row["起课方式"] or "time", "正时起课"),
        "question": row["问事"] or "",
        "subject": row["标的"] or "",
        "day_gz": row["日干支"] or "",
        "keti": row["课体"] or "",
        "chuan": row["三传"] or "",
        "summary": row["摘要"] or "",
        "remarks": row["备注"] or "",
        "tags": row["标签"] or "",
    } for row in rows]


def _insert_daliuren_record(dt_str, params, question, subject, pan, summary,
                            remarks="", tags=""):
    """写入一条大六壬记录，返回新记录 id。"""
    params = dlr_normalize_options(params)
    with get_connection() as cnx:
        ensure_daliuren_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO daliuren_records
            (时间, 起课方式, 参数, 问事, 标的, 备注, 标签, 日干支, 课体, 三传, 摘要)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dt_str, params['method'], json.dumps(params, ensure_ascii=False),
             question, subject, remarks, tags, pan['day_gz'], pan['keti'],
             '→'.join(pan['chuan']), summary),
        )
        cnx.commit()
        return cursor.lastrowid


def _render_daliuren(dt, params, record_id=None, question="", subject="",
                     remarks="", tags="", error="", q=""):
    """渲染大六壬页面；参数非法时退回正时起课并保留提示。"""
    params = dlr_normalize_options(params)
    try:
        pan = dlr_calculate(dt, method=params['method'],
                            manual=params['manual'], options=params)
    except ValueError as e:
        params = dlr_normalize_options({**params, 'method': 'time'})
        pan = dlr_calculate(dt, method='time', options=params)
        error = error or str(e)
    except (TypeError, KeyError) as e:
        params = dlr_normalize_options({})
        pan = dlr_calculate(dt)
        error = error or f'参数有误，已按正时起课：{e}'

    return render_template(
        'daliuren.html',
        pan=pan,
        params=params,
        method_options=DLR_METHODS,
        yuejiang_rules=DLR_YUEJIANG_RULES,
        noble_rules=DLR_NOBLE_RULES,
        shehai_rules=DLR_SHEHAI_RULES,
        gan_options=DLR_GAN,
        zhi_options=DLR_ZHI,
        tianjiang=DLR_TIANJIANG,
        zongmen_info=ZONGMEN_INFO,
        date_value=dt.strftime('%Y-%m-%d'),
        time_value=dt.strftime('%H:%M'),
        records=get_daliuren_records(q),
        search_q=q,
        record_id=record_id,
        question=question,
        subject=subject,
        remarks=remarks,
        tags=tags,
        error=error,
        summary=dlr_summary(pan),
    )


@app.route('/daliuren', methods=['GET', 'POST'])
def daliuren_index():
    """大六壬排盘：GET 起课（可带 ?record_id=N 载入历史），POST 保存。"""
    if request.method == 'GET':
        record_id = request.args.get('record_id')
        if record_id:
            try:
                rid = int(record_id)
                with get_connection() as cnx:
                    ensure_daliuren_table(cnx)
                    row = cnx.execute(
                        "SELECT * FROM daliuren_records WHERE id = ?", (rid,)
                    ).fetchone()
                if row:
                    try:
                        saved = json.loads(row["参数"] or '{}')
                    except (ValueError, TypeError):
                        saved = {}
                    dt = datetime.strptime(row["时间"], "%Y-%m-%d %H:%M")
                    return _render_daliuren(
                        dt, saved, record_id=rid,
                        question=row["问事"] or "", subject=row["标的"] or "",
                        remarks=row["备注"] or "", tags=row["标签"] or "",
                        q=request.args.get('q', ''),
                    )
            except (ValueError, TypeError):
                pass

    values = request.values
    params = _dlr_params_from(values)
    date_str, time_str = values.get('date'), values.get('time')
    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            dt = datetime.now()
    else:
        dt = datetime.now()

    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        subject = request.form.get('subject', '').strip()
        remarks = request.form.get('remarks', '')
        tags = request.form.get('tags', '').strip()
        error = ""
        try:
            if not question:
                error = "请填写问事（所问何事）"
            else:
                pan = dlr_calculate(dt, method=params['method'],
                                    manual=params['manual'], options=params)
                record_id = _insert_daliuren_record(
                    dt.strftime("%Y-%m-%d %H:%M"), params, question, subject,
                    pan, dlr_summary(pan), remarks=remarks, tags=tags,
                )
                return redirect(url_for('daliuren_index', record_id=record_id))
        except Exception as e:
            print(e)
            error = f"保存失败: {e}"

        return _render_daliuren(
            dt, params, question=question, subject=subject,
            remarks=remarks, tags=tags, error=error,
            q=values.get('q', ''),
        )

    return _render_daliuren(dt, params, q=values.get('q', ''))


@app.route('/daliuren/api')
def daliuren_api():
    """大六壬 JSON 接口（供校验与局部刷新使用）。"""
    params = _dlr_params_from(request.args)
    date_str, time_str = request.args.get('date'), request.args.get('time')
    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            return jsonify({'error': True, 'message': '无效的日期时间'}), 400
    else:
        dt = datetime.now()
    try:
        return jsonify(dlr_calculate(dt, method=params['method'],
                                     manual=params['manual'], options=params))
    except ValueError as e:
        return jsonify({'error': True, 'message': str(e)}), 400
    except Exception as e:
        print(f'大六壬 API 错误: {e}')
        return jsonify({'error': True, 'message': str(e)}), 500


@app.route('/daliuren/delete', methods=['POST'])
def daliuren_delete():
    try:
        data = request.json or {}
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_daliuren_table(cnx)
            cursor = cnx.execute("DELETE FROM daliuren_records WHERE id = ?",
                                 (record_id,))
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/daliuren/update', methods=['POST'])
def daliuren_update():
    """历史记录编辑：问事、标的、备注、标签（问事仍为必填）。"""
    try:
        data = request.json or {}
        record_id = data.get('record_id')
        question = (data.get('question') or '').strip()
        if not record_id:
            return jsonify({"status": "error", "message": "缺少记录编号"}), 400
        if not question:
            return jsonify({"status": "error", "message": "问事不能为空"}), 400
        with get_connection() as cnx:
            ensure_daliuren_table(cnx)
            cnx.execute(
                """UPDATE daliuren_records
                   SET 问事 = ?, 标的 = ?, 备注 = ?, 标签 = ? WHERE id = ?""",
                (question, data.get('subject') or '', data.get('remarks') or '',
                 data.get('tags') or '', record_id),
            )
            cnx.commit()
        return jsonify({"status": "success", "message": "记录已更新"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# 紫微斗数
# 排盘（安星、四化、运限）全部由前端 iztro 完成，服务端只负责记录的读写；
# 「时间」字段即出生时间，载入记录时用它重新排盘。因此这里不引入任何排盘依赖。
# ---------------------------------------------------------------------------

def get_ziwei_records(q=""):
    """查询紫微记录（供页面内记录切换使用）。"""
    records = []
    with get_connection() as cnx:
        ensure_ziwei_table(cnx)
        query = "SELECT * FROM ziwei_records WHERE 1=1"
        params = []
        if q:
            query += " AND (姓名 LIKE ? OR 标签 LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])
        query += " ORDER BY id DESC LIMIT 60"
        rows = cnx.execute(query, params).fetchall()
    for row in rows:
        records.append({
            "id": row["id"],
            "time": row["时间"] or "",
            "name": row["姓名"] or "",
            "gender": row["性别"] or "男",
            "pillars": row["四柱"] or "",
            "five_elements": row["五行局"] or "",
            "soul": row["命主"] or "",
            "body": row["身主"] or "",
            "tags": row["标签"] or "",
            "remarks": row["备注"] or "",
        })
    return records


def _get_ziwei_record(record_id):
    """读取单条紫微记录，返回模板可直接使用的字典。"""
    with get_connection() as cnx:
        ensure_ziwei_table(cnx)
        row = cnx.execute(
            "SELECT * FROM ziwei_records WHERE id = ?", (record_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "time": row["时间"] or "",
        "name": row["姓名"] or "",
        "gender": row["性别"] or "男",
        "pillars": row["四柱"] or "",
        "five_elements": row["五行局"] or "",
        "soul": row["命主"] or "",
        "body": row["身主"] or "",
        "tags": row["标签"] or "",
        "remarks": row["备注"] or "",
        "fix_leap": (row["闰月调整"] or "是") == "是",
        "school": row["流派"] or "",
    }


def _insert_ziwei_record(date_str_full, name, gender, pillars, five_elements,
                         soul, body, tags="", remarks="", fix_leap=True,
                         school=""):
    """写入一条紫微记录，返回新记录 id。"""
    dt = datetime.strptime(date_str_full, "%Y-%m-%d %H:%M")
    with get_connection() as cnx:
        ensure_ziwei_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO ziwei_records
            (时间, 姓名, 性别, 四柱, 五行局, 命主, 身主, 标签, 备注, 闰月调整, 流派)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dt.strftime("%Y-%m-%d %H:%M"), name, gender, pillars,
                five_elements, soul, body, tags, remarks,
                "是" if fix_leap else "否", school,
            ),
        )
        cnx.commit()
        return cursor.lastrowid


def _render_ziwei_page(record=None, error="", q=""):
    """渲染紫微页面；``record`` 非空时前端会用它的出生信息重新排盘。"""
    return render_template(
        "ziwei.html",
        records=get_ziwei_records(q),
        record=record,
        q=q,
        error=error,
    )


@app.route('/ziwei', methods=['GET', 'POST'])
def ziwei_index():
    """紫微斗数已并入命理页，重定向到 /mingli?tab=ziwei 以保持旧链接可用。"""
    return redirect(url_for('mingli_index', tab='ziwei'))
@app.route('/ziwei/update_remarks', methods=['POST'])
def ziwei_update_remarks():
    try:
        data = request.json
        record_id = data.get('record_id')
        remarks = data.get('remarks')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_ziwei_table(cnx)
            cnx.execute(
                "UPDATE ziwei_records SET 备注 = ? WHERE id = ?", (remarks, record_id)
            )
            cnx.commit()
        return jsonify({"status": "success", "message": "备注更新成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ziwei/delete', methods=['POST'])
def ziwei_delete():
    try:
        data = request.json
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_ziwei_table(cnx)
            cursor = cnx.execute("DELETE FROM ziwei_records WHERE id = ?", (record_id,))
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


# ===========================================================================
# 命理（八字 + 紫微斗数）—— 统一档案表 mingli_records
# 八字在服务端排盘，紫微在浏览器端由 iztro 排盘，二者共享同一份出生档案。
# ===========================================================================

MINGLI_TABS = ("bazi", "ziwei")


def _gz_or_none(gan, zhi):
    """干支合并；两个都为空表示交给排盘程序自动推算。"""
    gan, zhi = (gan or "").strip(), (zhi or "").strip()
    if gan and zhi:
        return gan + zhi
    if gan or zhi:
        raise ValueError("干支需要同时选择天干与地支")
    return None


def get_mingli_records(q=""):
    """查询命理档案列表（供页面内档案切换使用）。"""
    records = []
    with get_connection() as cnx:
        ensure_mingli_table(cnx)
        query = "SELECT * FROM mingli_records WHERE 1=1"
        params = []
        if q:
            query += " AND (姓名 LIKE ? OR 标签 LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])
        query += " ORDER BY id DESC LIMIT 60"
        rows = cnx.execute(query, params).fetchall()
    for row in rows:
        records.append({
            "id": row["id"],
            "time": row["时间"] or "",
            "gender": row["性别"] or "男",
            "name": row["姓名"] or "",
            "tags": row["标签"] or "",
            "remarks": row["备注"] or "",
        })
    return records


def _get_mingli_row(record_id):
    with get_connection() as cnx:
        ensure_mingli_table(cnx)
        return cnx.execute(
            "SELECT * FROM mingli_records WHERE id = ?", (record_id,)
        ).fetchone()


def _insert_mingli_record(subject, gender, date_str_full, pillars, tags="",
                          remarks="", solar_minutes=0, hour_unknown=False):
    """写入一条命理档案，返回新记录 id。"""
    dt = datetime.strptime(date_str_full, "%Y-%m-%d %H:%M")
    hg, hz = ("", "") if hour_unknown else (pillars[3][0], pillars[3][1])
    with get_connection() as cnx:
        ensure_mingli_table(cnx)
        cursor = cnx.execute(
            """
            INSERT INTO mingli_records
            (时间, 姓名, 性别, 标签, 备注, 校正分钟, 时柱未知,
             年干, 年支, 月干, 月支, 日干, 日支, 时干, 时支, 四柱)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dt.strftime("%Y-%m-%d %H:%M"), subject, gender, tags, remarks,
                str(solar_minutes), "是" if hour_unknown else "否",
                pillars[0][0], pillars[0][1], pillars[1][0], pillars[1][1],
                pillars[2][0], pillars[2][1], hg, hz, " ".join(pillars),
            ),
        )
        cnx.commit()
        return cursor.lastrowid


def _update_mingli_record(record_id, subject, gender, date_str_full, pillars,
                          tags="", remarks="", solar_minutes=0,
                          hour_unknown=False):
    """更新一条命理档案，返回是否成功。"""
    dt = datetime.strptime(date_str_full, "%Y-%m-%d %H:%M")
    hg, hz = ("", "") if hour_unknown else (pillars[3][0], pillars[3][1])
    with get_connection() as cnx:
        ensure_mingli_table(cnx)
        cursor = cnx.execute(
            """
            UPDATE mingli_records SET
                时间 = ?, 姓名 = ?, 性别 = ?, 标签 = ?, 备注 = ?,
                校正分钟 = ?, 时柱未知 = ?,
                年干 = ?, 年支 = ?, 月干 = ?, 月支 = ?,
                日干 = ?, 日支 = ?, 时干 = ?, 时支 = ?, 四柱 = ?
            WHERE id = ?
            """,
            (
                dt.strftime("%Y-%m-%d %H:%M"), subject, gender, tags, remarks,
                str(solar_minutes), "是" if hour_unknown else "否",
                pillars[0][0], pillars[0][1], pillars[1][0], pillars[1][1],
                pillars[2][0], pillars[2][1], hg, hz, " ".join(pillars),
                record_id,
            ),
        )
        cnx.commit()
        return cursor.rowcount > 0


def _render_mingli(**ctx):
    """渲染命理页；未显式传入的变量给出安全默认值。"""
    base = dict(
        records=[], record=None, record_id=None, tab="bazi", q="",
        new_record=False, edit_record=False, edit_id="", open_archive=False,
        subject="", gender="男", tags="", date_str="", hour=0, minute=0,
        solar_minutes=0, hour_unknown=False,
        year_gan="", year_zhi="", month_gan="", month_zhi="",
        day_gan="", day_zhi="", hour_gan="", hour_zhi="",
        is_history=False, result_data=None, error="",
    )
    base.update(ctx)
    return render_template("mingli.html", **base)


def _render_mingli_record(record_id, tab="bazi", open_archive=False,
                          edit_record=False):
    """载入指定档案并渲染（八字结果在服务端算好，紫微交给前端）。"""
    row = _get_mingli_row(record_id)
    if not row:
        return "Record not found", 404

    dt = datetime.strptime(row["时间"], "%Y-%m-%d %H:%M")
    hour_unknown = (row["时柱未知"] or "") == "是"
    solar_minutes = int(row["校正分钟"] or 0)

    result_data = None
    error = ""
    try:
        app, _bazi_text = perform_bazi(
            row["姓名"] or "", row["性别"] or "男",
            dt.year, dt.month, dt.day, dt.hour, dt.minute,
            gz_year=_gz_or_none(row["年干"], row["年支"]),
            gz_month=_gz_or_none(row["月干"], row["月支"]),
            gz_day=_gz_or_none(row["日干"], row["日支"]),
            gz_hour=_gz_or_none(row["时干"], row["时支"]),
            solar_minutes=solar_minutes,
            hour_unknown=hour_unknown,
        )
        result_data = app.get_data()
    except Exception as e:      # 八字排盘失败不应阻断紫微页
        print(e)
        error = f"八字排盘失败：{e}"

    return _render_mingli(
        records=get_mingli_records(),
        record={
            "id": row["id"],
            "time": row["时间"] or "",
            "name": row["姓名"] or "",
            "gender": row["性别"] or "男",
            "tags": row["标签"] or "",
            "remarks": row["备注"] or "",
        },
        record_id=record_id,
        tab=tab,
        new_record=edit_record,
        edit_record=edit_record,
        edit_id=record_id if edit_record else "",
        open_archive=open_archive,
        subject=row["姓名"] or "",
        gender=row["性别"] or "男",
        tags=row["标签"] or "",
        solar_minutes=solar_minutes,
        hour_unknown=hour_unknown,
        date_str=dt.strftime("%Y-%m-%d"),
        hour=dt.hour,
        minute=dt.minute,
        year_gan=row["年干"] or "", year_zhi=row["年支"] or "",
        month_gan=row["月干"] or "", month_zhi=row["月支"] or "",
        day_gan=row["日干"] or "", day_zhi=row["日支"] or "",
        hour_gan=row["时干"] or "", hour_zhi=row["时支"] or "",
        is_history=not edit_record,
        result_data=result_data,
        error=error,
    )


@app.route('/mingli', methods=['GET', 'POST'])
def mingli_index():
    """命理主页：八字与紫微共用一套档案，通过 tab 切换。"""
    tab = request.form.get('tab') or request.args.get('tab') or 'bazi'
    if tab not in MINGLI_TABS:
        tab = 'bazi'
    q = request.args.get('q', '')

    if request.method == 'POST':
        try:
            edit_id = request.form.get('edit_id', '').strip()
            subject = request.form.get('subject', '').strip()
            gender = request.form.get('gender', '男')
            tags = request.form.get('tags', '').strip()
            remarks = request.form.get('remarks', '')
            hour_unknown = request.form.get('hour_unknown') == 'on'
            solar_minutes = int(request.form.get('solar_minutes') or 0)
            date_str = request.form.get('date')
            if hour_unknown:
                hour = minute = 0
            else:
                hour = int(request.form.get('hour'))
                minute = int(request.form.get('minute'))
            dt = datetime.strptime(date_str, '%Y-%m-%d')

            gz_year = _gz_or_none(request.form.get('year_gan'),
                                  request.form.get('year_zhi'))
            gz_month = _gz_or_none(request.form.get('month_gan'),
                                   request.form.get('month_zhi'))
            gz_day = _gz_or_none(request.form.get('day_gan'),
                                 request.form.get('day_zhi'))
            gz_hour = _gz_or_none(request.form.get('hour_gan'),
                                  request.form.get('hour_zhi'))

            app, _bazi_text = perform_bazi(
                subject, gender, dt.year, dt.month, dt.day, hour, minute,
                gz_year=gz_year, gz_month=gz_month, gz_day=gz_day,
                gz_hour=gz_hour, solar_minutes=solar_minutes,
                hour_unknown=hour_unknown,
            )
            pillars = [p['ganzhi'] for p in app.pillars]
            date_str_full = f"{dt.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}"

            if edit_id:
                record_id = int(edit_id)
                if not _update_mingli_record(
                    record_id, subject, gender, date_str_full, pillars,
                    tags=tags, remarks=remarks, solar_minutes=solar_minutes,
                    hour_unknown=hour_unknown,
                ):
                    raise ValueError('记录不存在')
            else:
                record_id = _insert_mingli_record(
                    subject, gender, date_str_full, pillars,
                    tags=tags, remarks=remarks, solar_minutes=solar_minutes,
                    hour_unknown=hour_unknown,
                )
            return redirect(url_for('mingli_index', record_id=record_id, tab=tab))
        except Exception as e:
            print(e)
            return _render_mingli(
                error=f'发生错误: {e}', tab=tab, q=q,
                records=get_mingli_records(q),
                new_record=True,
                subject=request.form.get('subject', ''),
                gender=request.form.get('gender', '男'),
                tags=request.form.get('tags', ''),
                date_str=request.form.get('date', ''),
                solar_minutes=request.form.get('solar_minutes', 0),
                hour_unknown=request.form.get('hour_unknown') == 'on',
            )

    # ---------- GET ----------
    edit_id = request.args.get('edit_id')
    if edit_id:
        try:
            return _render_mingli_record(int(edit_id), tab, edit_record=True)
        except (ValueError, TypeError):
            pass

    record_id = request.args.get('record_id')
    if record_id:
        try:
            return _render_mingli_record(
                int(record_id), tab,
                open_archive=request.args.get('archive') == '1',
            )
        except (ValueError, TypeError):
            pass

    records = get_mingli_records(q)
    if records and request.args.get('new') != '1':
        return redirect(url_for(
            'mingli_index', record_id=records[0]['id'], tab=tab,
            archive='1' if request.args.get('archive') == '1' else None,
        ))

    now = datetime.now()
    return _render_mingli(
        tab=tab, q=q, records=records, new_record=True,
        date_str=now.strftime('%Y-%m-%d'), hour=now.hour, minute=now.minute,
        open_archive=request.args.get('archive') == '1',
    )


@app.route('/mingli/delete', methods=['POST'])
def mingli_delete():
    try:
        data = request.json
        record_id = data.get('record_id')
        if not record_id:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400
        with get_connection() as cnx:
            ensure_mingli_table(cnx)
            cursor = cnx.execute(
                "DELETE FROM mingli_records WHERE id = ?", (record_id,)
            )
            cnx.commit()
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success", "message": "删除成功"})
    except Exception as e:
        print(e)
        return jsonify({"status": "error", "message": str(e)}), 500


def run_web():
    print("启动 Web 服务...")
    print("请在浏览器访问 http://127.0.0.1:5000")
    Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, port=5000)

if __name__ == '__main__':
    run_web()
