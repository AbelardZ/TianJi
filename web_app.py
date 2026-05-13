# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from divination import perform_divination, create_wapp
import webbrowser
from threading import Timer
import re
from db import ensure_year_table, get_connection, initialize_database, quote_identifier

app = Flask(__name__)
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

    return render_template('history.html', 
                         results=results,
                         available_years=available_years,
                         current_year=year_table,
                         search_date=search_date,
                         search_subject=search_subject,
                         search_user=search_user)

@app.route('/history/view/<year_table>/<int:record_id>')
def view_history(year_table, record_id):
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
        
        return render_template('index.html',
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
            is_history=True 
        )

    except Exception as e:
        print(f"Error viewing history: {e}")
        return f"Error: {e}", 500

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

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    result_data = None
    subject = ""
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

    return render_template('index.html', 
                           result=result, 
                           result_data=result_data,
                           subject=subject, 
                           date_str=date_str, 
                           hour=hour, 
                           minute=minute,
                           yao_list=yao_list,
                           input_mode=input_mode,
                           ygua_codes=ygua_codes,
                           ganzhi_info=ganzhi_info,
                           year_gan=request.form.get('year_gan', ''),
                           year_zhi=request.form.get('year_zhi', ''),
                           month_gan=request.form.get('month_gan', ''),
                           month_zhi=request.form.get('month_zhi', ''),
                           day_gan=request.form.get('day_gan', ''),
                           day_zhi=request.form.get('day_zhi', ''),
                           hour_gan=request.form.get('hour_gan', ''),
                           hour_zhi=request.form.get('hour_zhi', ''))

def run_web():
    print("启动 Web 服务...")
    print("请在浏览器访问 http://127.0.0.1:5000")
    Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, port=5000)

if __name__ == '__main__':
    run_web()
