from flask import Blueprint, render_template, request, jsonify
from extensions import mysql
import json

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
def dashboard_home():
    # Ambil parameter filter dari request
    warehouse_filter = request.args.get('warehouse')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    cursor = mysql.connection.cursor()

    # Query untuk total stok per Item Group (dengan filter)
    query_item_group = """
        SELECT `Item Group`, SUM(`Jumlah Stok`) AS total_quantity
        FROM NTE
        JOIN stok ON NTE.IDNTE = stok.IDNTE
        WHERE 1=1
    """
    params = []
    if warehouse_filter:
        query_item_group += " AND stok.IDwarehouse = %s"
        params.append(warehouse_filter)
    if start_date and end_date:
        query_item_group += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    query_item_group += " GROUP BY `Item Group`"
    cursor.execute(query_item_group, tuple(params))
    item_group_data = cursor.fetchall()

    # Query untuk distribusi stok per Warehouse
    query_warehouse = """
        SELECT warehouse.`WH/SO`, SUM(stok.`Jumlah Stok`) AS total_quantity
        FROM stok
        JOIN warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
        WHERE 1=1
    """
    params = []
    if start_date and end_date:
        query_warehouse += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    query_warehouse += " GROUP BY warehouse.`WH/SO`"
    cursor.execute(query_warehouse, tuple(params))
    warehouse_data = cursor.fetchall()

    # Query untuk rata-rata stok per Tanggal Masuk
    query_sum_stock = """
        SELECT DATE(stok.`Tanggal Masuk`) AS date, sum(stok.`Jumlah Stok`) AS total_quantity
        FROM stok
        WHERE 1=1
    """
    params = []
    if warehouse_filter:
        query_sum_stock += " AND stok.IDwarehouse = %s"
        params.append(warehouse_filter)
    if start_date and end_date:
        query_sum_stock += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    query_sum_stock += " GROUP BY DATE(stok.`Tanggal Masuk`) ORDER BY date"
    cursor.execute(query_sum_stock, tuple(params))
    sum_stock_per_date = cursor.fetchall()

    # Query untuk status stok
    query_stock_status = """
        SELECT `Status Stok`, SUM(`Jumlah Stok`) AS total
        FROM stok
        WHERE 1=1
    """
    params = []
    if warehouse_filter:
        query_stock_status += " AND stok.IDwarehouse = %s"
        params.append(warehouse_filter)
    if start_date and end_date:
        query_stock_status += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    query_stock_status += " GROUP BY `Status Stok`"
    cursor.execute(query_stock_status, tuple(params))
    stock_status_data = cursor.fetchall()

    # Query untuk dropdown warehouse
    cursor.execute("SELECT IDwarehouse, `WH/SO` FROM warehouse")
    warehouses = cursor.fetchall()

# Query untuk mixed chart (stock by sub jenis)
 # Initial mixed chart query
    query_sub_jenis = """
    SELECT 
        DATE(s.`Tanggal Masuk`) as date,
        SUM(s.`Jumlah Stok`) as total_stock
    FROM stok s
    JOIN NTE n ON s.IDNTE = n.IDNTE
    WHERE DATE(s.`Tanggal Masuk`)
    GROUP BY DATE(s.`Tanggal Masuk`)
    ORDER BY date
    """
    cursor.execute(query_sub_jenis)
    results = cursor.fetchall()

    dates = []
    total_data = []
    growth_data = []
    prev_value = None

    for row in results:
        date_str = row['date'].strftime('%Y-%m-%d')
        current_value = float(row['total_stock'])
        
        dates.append(date_str)
        total_data.append(current_value)
        
        if prev_value is None or prev_value == 0:
            growth = 0
        else:
            growth = ((current_value - prev_value) / prev_value * 100)
        growth_data.append(round(growth, 2))
        
        prev_value = current_value

    mixed_chart_data = {
        'labels': dates,
        'datasets': [
            {
                'label': 'Total',
                'type': 'bar',
                'data': total_data,
                'backgroundColor': 'rgb(204, 43, 82)',
                'yAxisID': 'y',
                'order': 2
            },
            {
                'label': 'Growth',
                'type': 'line',
                'data': growth_data,
                'borderColor': 'rgb(75, 192, 192)',
                'borderWidth': 2,
                'fill': False,
                'tension': 0.4,
                'yAxisID': 'y1',
                'order': 1
            }
        ]
    }
      # Tambahkan query untuk mengambil unique Item Group
    query_item_groups = """
    SELECT DISTINCT `Item Group`
    FROM nte
    ORDER BY `Item Group`;
    """
    cursor.execute(query_item_groups)
    item_groups = cursor.fetchall()

    # Query untuk data awal double line chart
    query_double_line = """
    SELECT 
        DATE(stok.`Tanggal Masuk`) as entry_date,
        DATE_FORMAT(stok.`Tanggal Masuk`, '%y-%m-%d') as date_label,
        AVG(stok.`Jumlah Stok`) as avg_stock
    FROM stok
    GROUP BY entry_date, date_label 
    ORDER BY entry_date
    """
    cursor.execute(query_double_line)
    double_line_results = cursor.fetchall()

    # Process data
    labels = []
    avg_stock = []
    growth_rate = []
    prev_stock = None

    for row in double_line_results:
        current_stock = float(row['avg_stock'])
        labels.append(row['date_label'])
        avg_stock.append(current_stock)
        
        if prev_stock is None or prev_stock == 0:
            growth = 0
        else:
            growth = ((current_stock - prev_stock) / prev_stock * 100)
        growth_rate.append(round(growth, 2))
        
        prev_stock = current_stock

    double_line_chart_data = {
        "labels": labels,
        "avgStock": avg_stock,
        "growthRate": growth_rate
    }

    # Query untuk mendapatkan data stok terbaru dari inventori
    query_recent_stock = """
        SELECT 
            witel.namawitel,
            sto.KodeSTO,
            warehouse.`WH/SO`,
            NTE.`Item Group`,
            NTE.Jenis,
            NTE.`Merek NTE`,
            NTE.`Type NTE`,
            stok.`Status Stok`,
            stok.`Jumlah Stok`,
            stok.`Tanggal Masuk`
        FROM NTE
        JOIN stok ON NTE.IDNTE = stok.IDNTE
        JOIN warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
        JOIN witel ON warehouse.witelID = witel.witelID
        JOIN sto ON warehouse.IDwarehouse = sto.IDwarehouse
        WHERE 1=1
    """
    params = []
    if warehouse_filter:
        query_recent_stock += " AND warehouse.IDwarehouse = %s"
        params.append(warehouse_filter)
    if start_date and end_date:
        query_recent_stock += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    query_recent_stock += " ORDER BY stok.`Tanggal Masuk`desc"

    cursor.execute(query_recent_stock, tuple(params))
    recent_stocks = cursor.fetchall()

    # Gabungkan data yang memiliki Item Group, Jenis, Merek NTE, Type NTE, Status Stok, dan Tanggal Masuk yang sama
    combined_stocks = {}
    for stock in recent_stocks:
        key = (
            stock['Item Group'],
            stock['Jenis'],
            stock['Merek NTE'],
            stock['Type NTE'],
            stock['Status Stok'],
            stock['Tanggal Masuk'],
        )
        if key not in combined_stocks:
            combined_stocks[key] = {
                'Item Group': stock['Item Group'],
                'Jenis': stock['Jenis'],
                'Merek NTE': stock['Merek NTE'],
                'Type NTE': stock['Type NTE'],
                'Status Stok': stock['Status Stok'],
                'Jumlah Stok': stock['Jumlah Stok'],
                'namawitel': stock['namawitel'],
                'Tanggal Masuk': stock['Tanggal Masuk']
            }
        else:
            combined_stocks[key]['Jumlah Stok'] += stock['Jumlah Stok']

    # Konversi ke list untuk dikirimkan ke template
    combined_stocks_list = list(combined_stocks.values())

    cursor.close()

    # Format data untuk charts
    item_group_chart_data = {
        "labels": [row['Item Group'] for row in item_group_data],
        "data": [float(row['total_quantity']) for row in item_group_data]
    }
    warehouse_chart_data = {
        "labels": [row['WH/SO'] for row in warehouse_data],
        "data": [float(row['total_quantity']) for row in warehouse_data]
    }
    sum_stock_chart_data = {
        "labels": [row['date'].strftime('%Y-%m-%d') for row in sum_stock_per_date],
        "data": [float(row['total_quantity']) for row in sum_stock_per_date]
    }
    stock_status_chart_data = {
        "labels": [row['Status Stok'] for row in stock_status_data],
        "data": [float(row['total']) for row in stock_status_data]
    }

    return render_template(
        'dashboard/dashboard.html',
        item_group_chart_data=json.dumps(item_group_chart_data),
        warehouse_chart_data=json.dumps(warehouse_chart_data),
        sum_stock_chart_data=json.dumps(sum_stock_chart_data),
        stock_status_chart_data=json.dumps(stock_status_chart_data),
        mixed_chart_data=json.dumps(mixed_chart_data),
        double_line_chart_data=json.dumps(double_line_chart_data),
        item_groups=item_groups,
        warehouses=warehouses,
        selected_warehouse=warehouse_filter,
        selected_start_date=start_date,
        selected_end_date=end_date,
        recent_stocks=combined_stocks_list
    )

# Endpoint untuk menampilkan form input stok
@dashboard_bp.route('/add-stock', methods=['GET', 'POST'])
def add_stock():
    if request.method == 'POST':
        # Ambil data dari form
        item_group = request.form.get('item_group')
        jenis = request.form.get('jenis')
        merek_nte = request.form.get('merek_nte')
        type_nte = request.form.get('type_nte')
        status_stok = request.form.get('status_stok')
        jumlah = request.form.get('jumlah')
        witel = request.form.get('witel')
        
        cursor = mysql.connection.cursor()
        # Query untuk menambahkan data stok
        query = """
            INSERT INTO stok (`Item Group`, `Jenis`, `Merek NTE`, `Type NTE`, `Status Stok`, `Jumlah`, `Witel`)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (item_group, jenis, merek_nte, type_nte, status_stok, jumlah, witel))
        mysql.connection.commit()
        cursor.close()
        
        # Ambil data yang baru dimasukkan
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM stok WHERE `Item Group` = %s AND `Jenis` = %s AND `Merek NTE` = %s AND `Type NTE` = %s AND `Status Stok` = %s AND `Jumlah` = %s AND `Witel` = %s", 
                       (item_group, jenis, merek_nte, type_nte, status_stok, jumlah, witel))
        new_stock = cursor.fetchone()
        cursor.close()
        
        return jsonify({'message': 'Stock added successfully!', 'new_stock': new_stock}), 200

    # Jika request method adalah GET, tampilkan form input
    return render_template('dashboard/add_stock.html')

# Endpoint untuk filter bar chart
@dashboard_bp.route('/filter-item-group', methods=['POST'])
def filter_item_group():
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        cursor = mysql.connection.cursor()
    
        query = """
            SELECT `Item Group`, SUM(`Jumlah Stok`) AS total_quantity
            FROM NTE
            JOIN stok ON NTE.IDNTE = stok.IDNTE
            WHERE 1=1
        """
        params = []

        if warehouse_id:
            query += " AND stok.IDwarehouse = %s"
            params.append(warehouse_id)
        if start_date and end_date:
            query += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " GROUP BY `Item Group`"

        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()

        return jsonify({
            'labels': [row['Item Group'] for row in results],
            'data': [float(row['total_quantity']) for row in results]
        })

    except Exception as e:
        print(f"Error in filter_item_group: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint untuk filter pie chart
@dashboard_bp.route('/filter-warehouse', methods=['POST'])
def filter_warehouse():
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT warehouse.`WH/SO`, SUM(stok.`Jumlah Stok`) AS total_quantity
            FROM stok
            JOIN warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
            WHERE 1=1
        """
        params = []

        if warehouse_id:
            query += " AND stok.IDwarehouse = %s"
            params.append(warehouse_id)
        if start_date and end_date:
            query += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
            
        query += " GROUP BY warehouse.`WH/SO`"
        
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'labels': [row['WH/SO'] for row in results],
            'data': [float(row['total_quantity']) for row in results]
        })
        
    except Exception as e:
        print(f"Error in filter_warehouse: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint untuk filter line chart
@dashboard_bp.route('/filter-stock-date', methods=['POST'])
def filter_stock_date():
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT DATE(stok.`Tanggal Masuk`) AS date,
                   sum(stok.`Jumlah Stok`) AS total_quantity
            FROM stok
            WHERE 1=1
        """
        params = []
        
        if warehouse_id:
            query += " AND stok.IDwarehouse = %s"
            params.append(warehouse_id)
        if start_date and end_date:
            query += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
            
        query += " GROUP BY DATE(stok.`Tanggal Masuk`) ORDER BY date"
        
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()
        
        return jsonify({
            'labels': [row['date'].strftime('%Y-%m-%d') for row in results],
            'data': [float(row['total_quantity']) for row in results]
        })
        
    except Exception as e:
        print(f"Error in filter_stock_date: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Endpoint untuk filter stock status
@dashboard_bp.route('/filter-stock-status', methods=['POST'])
def filter_stock_status():
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        cursor = mysql.connection.cursor()
        
        query = """
            SELECT `Status Stok`, SUM(`Jumlah Stok`) as total
            FROM stok
            WHERE 1=1
        """
        params = []

        if warehouse_id:
            query += " AND stok.IDwarehouse = %s"
            params.append(warehouse_id)
        if start_date and end_date:
            query += " AND DATE(stok.`Tanggal Masuk`) BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        query += " GROUP BY `Status Stok`"
        
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()
        
        # Convert each row result from Decimal to float to make it JSON serializable
        results = [{'Status Stok': row['Status Stok'], 'total': float(row['total'])} for row in results]
        
        # Check if results is not empty
        if results:
            return jsonify({
                'labels': [row['Status Stok'] for row in results],
                'data': [row['total'] for row in results]
            })
        else:
            return jsonify({'labels': [], 'data': []})
        
    except Exception as e:
        print(f"Error in filter_stock_status: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    
# Update route filter-sub-jenis
@dashboard_bp.route('/filter-sub-jenis', methods=['POST'])
def filter_sub_jenis():
    try:
        data = request.get_json()
        warehouse_id = data.get('warehouse')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        item_group = data.get('item_group')
        
        cursor = mysql.connection.cursor()

        # Query untuk mengambil data berdasarkan item_group saja
        query = """
        SELECT 
            nte.`Item Group`,
            SUM(IFNULL(stok.`Jumlah Stok`, 0)) AS total_quantity
        FROM stok
        JOIN nte ON nte.IDNTE = stok.IDNTE
        WHERE 1=1
        """

        params = []

        # Menambahkan kondisi berdasarkan parameter yang diberikan
        if warehouse_id:
            query += " AND stok.IDwarehouse = %s"
            params.append(warehouse_id)
        if item_group:
            query += " AND nte.`Item Group` = %s"
            params.append(item_group)
        if start_date:
            query += " AND DATE(stok.`Tanggal Masuk`) >= %s"
            params.append(start_date)
        if end_date:
            query += " AND DATE(stok.`Tanggal Masuk`) <= %s"
            params.append(end_date)

        query += " GROUP BY nte.`Item Group` ORDER BY nte.`Item Group`"

        # Eksekusi query
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()

        # Debugging output untuk memastikan data yang diambil benar
        if not results:
            print("No data returned from query for Item Group.")
        else:
            for row in results:
                print(f"Item Group: {row['Item Group']}, Total Quantity: {row['total_quantity']}")

        # Extracting data from results
        item_groups = [row['Item Group'] for row in results]
        total_quantities = [int(row['total_quantity']) for row in results]

        response_data = {
            'itemGroups': item_groups,
            'totalQuantities': total_quantities
        }

        return jsonify(response_data)

    except Exception as e:
        print(f"Error in filter_sub_jenis: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route untuk double line chart
@dashboard_bp.route('/get-double-line-data', methods=['POST'])
def get_double_line_data():
    try:
        data = request.get_json()
        print(data) 
        warehouse_id = data.get('warehouse')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        cursor = mysql.connection.cursor()
        
        query = """
        SELECT 
            DATE(stok.`Tanggal Masuk`) as entry_date,
            DATE_FORMAT(stok.`Tanggal Masuk`, '%%Y-%%m-%d') as date_label,
            AVG(stok.`Jumlah Stok`) as avg_stock
        FROM stok
        WHERE 1=1
        """
        
        params = []
        
        if warehouse_id:
            query += " AND stok.IDwarehouse = %s"
            params.append(warehouse_id)
        if start_date:
            query += " AND DATE(stok.`Tanggal Masuk`) >= %s"
            params.append(start_date)
        if end_date:
            query += " AND DATE(stok.`Tanggal Masuk`) <= %s"
            params.append(end_date)
            
        query += " GROUP BY entry_date, date_label ORDER BY entry_date"
        
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()

        labels = []
        avg_stock = []
        growth_rate = []
        prev_stock = None
        
        for row in results:
            current_stock = float(row['avg_stock'])
            labels.append(row['date_label'])
            avg_stock.append(current_stock)
            
            # Hitung growth rate
            if prev_stock is None or prev_stock == 0:
                growth = 0
            else:
                growth = ((current_stock - prev_stock) / prev_stock * 100)
            growth_rate.append(round(growth, 2))
            
            prev_stock = current_stock
            
        cursor.close()
            
        return jsonify({
            'labels': labels,
            'avgStock': avg_stock,
            'growthRate': growth_rate
        })
        
    except Exception as e:
        print(f"Error in get_double_line_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

