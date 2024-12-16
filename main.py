from flask import Blueprint, render_template, request, redirect, url_for, flash,make_response
from extensions import mysql
import pandas as pd
from io import BytesIO

# Inisialisasi blueprint untuk inventory
main_bp = Blueprint('main_bp', __name__, url_prefix='/inventory')

# Menampilkan semua item di inventory dengan data dari tabel berelasi
@main_bp.route('/', methods=['GET'])
def inventory():
    try:
        cur = mysql.connection.cursor()

        # Query untuk mengambil data dari tabel `witel` dan `warehouse` untuk dropdown
        cur.execute("SELECT * FROM witel")
        witels = cur.fetchall()

        cur.execute("SELECT * FROM sto")
        stos = cur.fetchall()

        cur.execute("SELECT * FROM warehouse")
        warehouses = cur.fetchall()

        # Query untuk menggabungkan data dari tabel yang berelasi
        query = """
            SELECT
                NTE.IDNTE,
                NTE.`Item Group`,
                NTE.Jenis,
                NTE.`Merek NTE`,
                NTE.`Type NTE`,
                NTE.`Serial Number`,
                NTE.Segmentasi,
                stok.stokID,
                stok.`Status Stok`,
                stok.`Jumlah Stok`,
                stok.`Tanggal Masuk`,
                warehouse.`WH/SO`,
                witel.namawitel,
                sto.KodeSTO
            FROM
                NTE
            JOIN
                stok ON NTE.IDNTE = stok.IDNTE
            JOIN
                warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
            JOIN
                witel ON warehouse.witelID = witel.witelID
            LEFT JOIN     
                sto ON warehouse.IDwarehouse = sto.IDwarehouse
            ORDER BY stok.`Tanggal Masuk` ASC, witel.namawitel ASC, sto.KodeSTO ASC, NTE.`Item Group`;

        """
        cur.execute(query)
        items = cur.fetchall()
        print("Items:", items)
        cur.close()
    except Exception as e:
        flash(f'Error retrieving inventory data: {str(e)}', 'error')
        items = []
        witels = []
        warehouses = []
        stos = [] 


    return render_template('inventory/inventory-page.html', items=items, witels=witels, warehouses=warehouses, stos=stos)


# CREATE: Menambahkan data baru ke tabel yang berelasi
@main_bp.route('/add', methods=['POST'])
def add_item():
    if request.method == 'POST':
        try:
            cur = mysql.connection.cursor()
            
            def generate_id_by_jenis(jenis, cur):
                prefix_mapping = {
                    'ACC AP': 'ACC',
                    'AP': 'AP',
                    'ENTERPRISE': 'ENT',
                    'IP CAM': 'IPC',
                    'MODEM': 'MDM',
                    'NODE-B': 'NDB',
                    'ONT DUAL BAND': 'ODB',
                    'ONT PREMIUM': 'OPR',
                    'ONT SINGLE BAND': 'OSB',
                    'ORBIT': 'ORB',
                    'OTT BOX/INDIBOX': 'OTT',
                    'PLC': 'PLC',
                    'REMOTE': 'RMT',
                    'STB': 'STB',
                    'WIFI EXTENDER': 'WEX'
                }
                
                prefix = prefix_mapping.get(jenis, 'NTE')
                
                try:
                    # Ambil semua ID yang ada dengan prefix yang sama
                    cur.execute("SELECT IDNTE FROM nte WHERE IDNTE LIKE %s", (f"{prefix}%",))
                    existing_ids = [row[0] for row in cur.fetchall()]
                    
                    if existing_ids:
                        # Ekstrak nomor dari ID yang ada
                        existing_numbers = []
                        for id_str in existing_ids:
                            num_str = ''.join(filter(str.isdigit, id_str))
                            if num_str:
                                existing_numbers.append(int(num_str))
                        
                        if existing_numbers:
                            max_num = max(existing_numbers)
                            new_num = max_num + 1
                        else:
                            new_num = 1
                    else:
                        new_num = 1
                    
                    new_id = f"{prefix}{str(new_num).zfill(3)}"
                    print(f"Generated new ID: {new_id}")
                    return new_id
                    
                except Exception as e:
                    print(f"Error in ID generation: {str(e)}")
                    # Fallback: generate ID dengan timestamp
                    import time
                    timestamp = int(time.time())
                    return f"{prefix}{str(timestamp)[-3:]}"

            # Ambil dan validasi data form
            form_data = {
                'item_group': request.form.get('item_group'),
                'jenis': request.form.get('jenis'),
                'merk_nte': request.form.get('merk_nte'),
                'type_nte': request.form.get('type_nte'),
                'status_stok': request.form.get('status_stok'),
                'jumlah_stok': request.form.get('jumlah_stok'),
                'tanggal_masuk': request.form.get('tanggal_masuk'),
                'warehouse': request.form.get('warehouse'),
                'serial_number': request.form.get('serial_number', ''),
                'segmentasi': request.form.get('segmentasi', '')
            }

            # Validasi data wajib
            for key, value in form_data.items():
                if key != 'serial_number' and not value:
                    raise ValueError(f"Field {key} wajib diisi")

            print("Validated form data:", form_data)

            # Generate IDs
            new_nte_id = generate_id_by_jenis(form_data['jenis'], cur)
            import time, random
            stok_id = f"STK{int(time.time())}{random.randint(1000,9999)}"

            print(f"Final Generated IDs - NTE: {new_nte_id}, Stok: {stok_id}")

            # Insert ke tabel NTE
            nte_query = """
                INSERT INTO nte 
                (IDNTE, `Item Group`, Jenis, `Merek NTE`, `Type NTE`, `Serial Number`,Segmentasi) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            nte_values = (
                new_nte_id, 
                form_data['item_group'],
                form_data['jenis'],
                form_data['merk_nte'],
                form_data['type_nte'],
                form_data['serial_number'],
                form_data['segmentasi']
            )
            
            print("Executing NTE insert with values:", nte_values)
            cur.execute(nte_query, nte_values)

            # Insert ke tabel stok
            stok_query = """
                INSERT INTO stok 
                (stokID, IDNTE, IDwarehouse, `Status Stok`, `Jumlah Stok`, `Tanggal Masuk`) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            stok_values = (
                stok_id,
                new_nte_id,
                form_data['warehouse'],
                form_data['status_stok'],
                form_data['jumlah_stok'],
                form_data['tanggal_masuk']
            )
            
            print("Executing Stok insert with values:", stok_values)
            cur.execute(stok_query, stok_values)

            mysql.connection.commit()
            print("Transaction committed successfully")
            flash('Item berhasil ditambahkan!', 'success')

        except ValueError as e:
            mysql.connection.rollback()
            print(f"Validation error: {e}")
            flash(str(e), 'error')
            
        except Exception as e:
            mysql.connection.rollback()
            print(f"Database error: {e}")
            print(f"Error type: {type(e)}")
            print(f"Error args: {e.args}")
            flash(f'Error adding item: {str(e)}', 'error')
            
        finally:
            if 'cur' in locals():
                cur.close()

    print("Form data:", form_data)

    return redirect(url_for('main_bp.inventory'))

@main_bp.route('/filter', methods=['GET'])
def filter_data():
    # Mendapatkan parameter filter dari form
    search = request.args.get('search')
    witel = request.args.get('witel')
    item_group = request.args.get('item_group')
    daily = request.args.get('daily')

    # Query dasar untuk pengambilan data dengan filter
    query = """
    SELECT 
            witel.namawitel,
            sto.KodeSTO,
            warehouse.`WH/SO`,
            NTE.`Item Group`,
            NTE.Jenis,
            NTE.`Merek NTE`,
            NTE.`Type NTE`,
            NTE.`Serial Number`,
            NTE.`Segmentasi`,
            stok.`Status Stok`,
            stok.`Jumlah Stok`,
            stok.`Tanggal Masuk`,
            stok.IDNTE
        FROM NTE
        JOIN stok ON NTE.IDNTE = stok.IDNTE
        JOIN warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
        JOIN witel ON warehouse.witelID = witel.witelID
        JOIN sto ON warehouse.IDwarehouse = sto.IDwarehouse
    """
    
    where_clauses = []
    params = []

    #
    if search:
        where_clauses.append("(NTE.`Item Group` LIKE %s OR NTE.Jenis LIKE %s)")
        params.extend([f'%{search}%', f'%{search}%'])

    if witel:
        where_clauses.append("witel.namawitel = %s")
        params.append(witel)

    if item_group:
        where_clauses.append("NTE.`Item Group` = %s")
        params.append(item_group)

    if daily:
        where_clauses.append("DATE(stok.`Tanggal Masuk`) = %s")
        params.append(daily)

    # Add WHERE clause if there are any conditions
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    # Debug print
    print("Query:", query)
    print("Parameters:", params)
    
    # Execute query
    cur = mysql.connection.cursor()
    cur.execute(query, params)
    results = cur.fetchall()
    cur.close()

    return render_template('inventory/inventory-page.html', items=results)

# DELETE: Menghapus data berdasarkan IDNTE
@main_bp.route('/delete/<string:id>', methods=['GET'])
def delete_item(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM stok WHERE IDNTE = %s", [id])
        cur.execute("DELETE FROM NTE WHERE IDNTE = %s", [id])
        mysql.connection.commit()
        cur.close()

        flash('Item deleted successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error deleting item: {str(e)}', 'error')

    return redirect(url_for('main_bp.inventory'))

# UPDATE: Mengupdate data di inventory berdasarkan IDNTE
@main_bp.route('/edit/<string:id>', methods=['GET', 'POST'])
def edit_item(id):
    if request.method == 'POST':
        # Ambil data dari form untuk update
        item_group = request.form.get('item_group')
        jenis = request.form.get('jenis')
        merek_nte = request.form.get('merk_nte')
        type_nte = request.form.get('type_nte')
        serial_number = request.form.get('serial_number')
        segmentasi = request.form.get('segmentasi')
        status_stok = request.form.get('status_stok')
        jumlah_stok = request.form.get('jumlah_stok')
        tanggal_masuk = request.form.get('tanggal_masuk')
        warehouse_id = request.form.get('warehouse')

        try:
            cur = mysql.connection.cursor()
            # Update data di tabel NTE
            cur.execute("UPDATE NTE SET `Item Group` = %s, Jenis = %s, `Merek NTE` = %s, `Type NTE` = %s, `Serial Number` = %s, Segmentasi = %s WHERE IDNTE = %s",
                        (item_group, jenis, merek_nte, type_nte, serial_number, segmentasi, id))

            # Update data di tabel stok
            cur.execute("UPDATE stok SET `Status Stok` = %s, `Jumlah Stok` = %s, `Tanggal Masuk` = %s, IDwarehouse = %s WHERE IDNTE = %s",
                        (status_stok, jumlah_stok, tanggal_masuk, warehouse_id, id))

            mysql.connection.commit()
            cur.close()

            flash('Item updated successfully!', 'success')
            return redirect(url_for('main_bp.inventory'))

        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error updating item: {str(e)}', 'error')
            return redirect(url_for('main_bp.inventory'))

    elif request.method == 'GET':
        cur = mysql.connection.cursor()
        query = """
         SELECT
                NTE.IDNTE,
                NTE.`Item Group`,
                NTE.Jenis,
                NTE.`Merek NTE`,
                NTE.`Type NTE`,
                NTE.`Serial Number`,
                NTE.Segmentasi,
                stok.stokID,
                stok.`Status Stok`,
                stok.`Jumlah Stok`, 
                stok.`Tanggal Masuk`,
                warehouse.`WH/SO`,
                witel.namawitel,
                sto.KodeSTO
            FROM
                NTE
            JOIN
                stok ON NTE.IDNTE = stok.IDNTE
            JOIN
                warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
            JOIN
                witel ON warehouse.witelID = witel.witelID
            JOIN   
                sto ON warehouse.IDwarehouse = sto.IDwarehouse
            WHERE
                NTE.IDNTE = %s;
        """
        cur.execute(query, (id,))
        item = cur.fetchone()
        cur.close()

        if not item:
            flash('Item not found!', 'error')
            return redirect(url_for('main_bp.inventory'))

        # Ambil semua warehouses untuk dropdown
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM warehouse")
        warehouses = cur.fetchall()
        cur.close()

        # Ambil semua witel untuk dropdown
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM witel")
        witels = cur.fetchall()
        cur.close()

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM sto")
        stos = cur.fetchall()
        cur.close()

        return render_template('inventory/edit-page.html', item=item, warehouses=warehouses, witels=witels, stos=stos)

@main_bp.route('/export', methods=['GET'])
def export_inventory():
    try:
        # Ambil data inventory dari database
        cur = mysql.connection.cursor()
        query = """
             SELECT
                NTE.IDNTE,
                NTE.`Item Group`,
                NTE.Jenis,
                NTE.`Merek NTE`,
                NTE.`Type NTE`,
                NTE.`Serial Number`,
                NTE.Segmentasi,
                stok.stokID,
                stok.`Status Stok`,
                stok.`Jumlah Stok`,
                stok.`Tanggal Masuk`,
                warehouse.`WH/SO`,
                witel.namawitel,
                sto.KodeSTO
            FROM
                NTE
            JOIN
                stok ON NTE.IDNTE = stok.IDNTE
            JOIN
                warehouse ON stok.IDwarehouse = warehouse.IDwarehouse
            JOIN
                witel ON warehouse.witelID = witel.witelID
            LEFT JOIN     
                sto ON warehouse.IDwarehouse = sto.IDwarehouse;
        """
        cur.execute(query)
        data = cur.fetchall()

        print(data)
        # Konversi hasil query menjadi DataFrame pandas
        df = pd.DataFrame(data, columns=[
        'namawitel','KodeSTO','WH/SO','Status Stok','Item Group',
        'Jenis', 'Merek NTE', 'Type NTE', 'Serial Number', 'Jumlah Stok', 'Tanggal Masuk','Segmentasi'
        ])

        print(df.head())

        # Simpan DataFrame ke dalam file Excel
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Inventory Data')
        writer.close()
        output.seek(0)

        # Generate response untuk mengirimkan file Excel ke user
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=inventory_data.xlsx'
        response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response

    except Exception as e:
        return f"Error exporting data: {str(e)}"