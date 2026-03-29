import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
import math
import datetime

# --- Kết nối DB ---
conn = sqlite3.connect("xanh_sv.db")
c = conn.cursor()

# Tạo bảng người dùng
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    fullname TEXT
)
''')

# Tạo bảng xe đạp
c.execute('''
CREATE TABLE IF NOT EXISTS bikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT,
    owner TEXT,
    status TEXT,
    lat REAL,
    lon REAL
)
''')

# Tạo bảng lịch sử thuê
c.execute('''
CREATE TABLE IF NOT EXISTS rentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    bike_id INTEGER,
    owner TEXT,
    location TEXT,
    time TEXT
)
''')
conn.commit()

# --- Hàm xử lý ---
def register_user(username, password, fullname):
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, password, fullname))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    return c.fetchone()

def get_bikes():
    return pd.read_sql_query("SELECT * FROM bikes", conn)

def update_status(bike_id, new_status):
    c.execute("UPDATE bikes SET status=? WHERE id=?", (new_status, bike_id))
    conn.commit()

def add_bike(location, owner, lat, lon):
    c.execute("INSERT INTO bikes (location, owner, status, lat, lon) VALUES (?, ?, ?, ?, ?)",
              (location, owner, "Cho thuê", lat, lon))
    conn.commit()

def add_rental(username, bike_id, owner, location):
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO rentals (username, bike_id, owner, location, time) VALUES (?, ?, ?, ?, ?)",
              (username, bike_id, owner, location, time_now))
    conn.commit()

def get_rentals(username):
    return pd.read_sql_query("SELECT * FROM rentals WHERE username=?", conn, params=(username,))

# --- Hàm tính khoảng cách Haversine ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# --- Trang chủ ---
def home_page():
    st.title("🌱🚲 Xanh SV - Xe đạp thông minh, sống xanh mỗi ngày")
    st.write("Khám phá xe quanh bạn và đặt thuê ngay!")

    bikes = get_bikes()
    if bikes.empty:
        st.warning("Chưa có xe nào trong hệ thống.")
        return

    # Người dùng chọn vị trí hiện tại bằng bản đồ
    st.subheader("📍 Chọn vị trí hiện tại trên bản đồ")
    m = folium.Map(location=[10.7769, 106.7009], zoom_start=12)
    st.write("👉 Click vào bản đồ để chọn vị trí hiện tại")
    map_data = st_folium(m, width=700, height=500)

    if map_data and map_data["last_clicked"]:
        lat_user = map_data["last_clicked"]["lat"]
        lon_user = map_data["last_clicked"]["lng"]
        st.success(f"Vị trí hiện tại: {lat_user:.6f}, {lon_user:.6f}")

        # Gợi ý xe gần nhất
        bikes["distance_km"] = bikes.apply(lambda row: haversine(lat_user, lon_user, row["lat"], row["lon"]), axis=1)
        nearest = bikes.sort_values("distance_km").head(5)

        st.subheader("🚲 Xe gần bạn")
        for _, row in nearest.iterrows():
            st.markdown(f"**Xe ID {row['id']}** - {row['owner']} ({row['status']}) - {row['distance_km']:.2f} km")
            if row["status"] == "Cho thuê":
                if st.button(f"Thuê ngay xe {row['id']}"):
                    update_status(row["id"], "Đã được thuê")
                    add_rental(st.session_state["username"], row["id"], row["owner"], row["location"])
                    st.success(f"Bạn đã thuê xe ID {row['id']} thành công!")
            else:
                st.warning("Xe này hiện không khả dụng.")

        # Bản đồ hiển thị xe gần nhất
        m2 = folium.Map(location=[lat_user, lon_user], zoom_start=13)
        folium.Marker([lat_user, lon_user], popup="Vị trí của bạn", icon=folium.Icon(color="blue")).add_to(m2)
        for _, row in nearest.iterrows():
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=f"Xe ID {row['id']} - {row['owner']} ({row['status']}) - {row['distance_km']:.2f} km",
                tooltip=row["location"]
            ).add_to(m2)
        st_folium(m2, width=700, height=500)

    # Top khu vực được chọn nhiều
    st.subheader("📊 Khu vực được chọn nhiều")
    top_locations = bikes["location"].value_counts().head(5)
    st.bar_chart(top_locations)

# --- Trang quản lý xe ---
def manage_bike_page():
    st.title("🛠️ Quản lý xe đạp")
    st.write(f"Chào **{st.session_state['fullname']}** ({st.session_state['username']})")

    bikes = get_bikes()
    st.dataframe(bikes)

    st.subheader("Thêm xe mới")
    m = folium.Map(location=[10.7769, 106.7009], zoom_start=12)
    st.write("👉 Click vào bản đồ để chọn vị trí xe")
    map_data = st_folium(m, width=700, height=500)

    if map_data and map_data["last_clicked"]:
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        st.success(f"Bạn đã chọn vị trí: {lat:.6f}, {lon:.6f}")
        location = st.text_input("Khu vực")
        if st.button("Thêm xe"):
            add_bike(location, st.session_state["fullname"], lat, lon)
            st.success("Xe mới đã được thêm thành công!")

# --- Trang lịch sử thuê xe ---
def rental_history_page():
    st.title("📜 Lịch sử thuê xe")
    rentals = get_rentals(st.session_state["username"])
    if rentals.empty:
        st.info("Bạn chưa thuê xe nào.")
    else:
        st.dataframe(rentals)

# --- Trang lịch sử cho thuê xe ---
def owner_rental_history_page():
    st.title("📜 Lịch sử cho thuê xe của bạn")
    rentals = pd.read_sql_query("SELECT * FROM rentals WHERE owner=?", conn, params=(st.session_state["fullname"],))
    if rentals.empty:
        st.info("Xe của bạn chưa được ai thuê.")
    else:
        st.dataframe(rentals[["bike_id", "username", "location", "time"]])

        # Thống kê doanh thu giả định (20k VNĐ/lượt)
        st.subheader("💰 Thống kê doanh thu")
        total_rentals = len(rentals)
        revenue = total_rentals * 20000
        st.write(f"Số lượt thuê: {total_rentals}")
        st.write(f"Tổng doanh thu giả định: {revenue:,} VNĐ")

# --- Trang đăng nhập / đăng ký ---
def login_register_page():
    st.title("🔐 Đăng nhập / Đăng ký")
    choice = st.radio("Chọn hành động:", ["Đăng nhập", "Đăng ký"])

    username = st.text_input("Tên đăng nhập")
    password = st.text_input("Mật khẩu", type="password")

    if choice == "Đăng nhập":
        if st.button("Đăng nhập"):
            user = login_user(username, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["fullname"] = user[2]
                st.success(f"Xin chào {user[2]}! Bạn đã đăng nhập thành công.")
            else:
                st.error("Sai tên đăng nhập hoặc mật khẩu.")
    else:
        fullname = st.text_input("Tên hiển thị")
        if st.button("Đăng ký"):
            if register_user(username, password, fullname):
                st.success("Đăng ký thành công! Vui lòng đăng nhập.")
            else:
                st.error("Tên đăng nhập đã tồn tại.")

# --- Sidebar thương hiệu ---
st.sidebar.markdown("## 🚲 Xanh SV")
st.sidebar.markdown("_Xe đạp thông minh – Sống xanh mỗi ngày_")

# --- Trạng thái đăng nhập ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["fullname"] = ""

# --- Điều hướng ---
if not st.session_state["logged_in"]:
    login_register_page()
else:
    st.sidebar.markdown(f"👤 Người dùng: **{st.session_state['fullname']}**")
    if st.sidebar.button("Đăng xuất"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["fullname"] = ""
        st.success("Bạn đã đăng xuất thành công.")

    page = st.sidebar.radio("Chọn trang:", 
                            ["Trang chủ", "Quản lý xe", "Lịch sử thuê xe", "Lịch sử cho thuê"])
    if page == "Trang chủ":
        home_page()
    elif page == "Quản lý xe":
        manage_bike_page()
    elif page == "Lịch sử thuê xe":
        rental_history_page()
    elif page == "Lịch sử cho thuê":
        owner_rental_history_page()