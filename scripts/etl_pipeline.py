import pandas as pd
import boto3

# ==============================
# AWS S3 CONFIGURATION
# ==============================
bucket_name = 'ecommerce-sales-pipeline-2026'
customer_file_key = 'raw-data/customer.csv'
product_file_key = 'raw-data/product.csv'
sales_file_key = 'raw-data/sales.csv'
processed_file_key = 'processed-data/final_processed_data.csv'
dashboard_file_key = 'processed-data/dashboard.html'

# ==============================
# CREATE S3 CLIENT
# ==============================
s3 = boto3.client('s3')
print("Connected to AWS S3")

# ==============================
# DOWNLOAD FILES FROM S3
# ==============================
s3.download_file(bucket_name, customer_file_key, '../raw_data/customer.csv')
s3.download_file(bucket_name, product_file_key,  '../raw_data/product.csv')
s3.download_file(bucket_name, sales_file_key,    '../raw_data/sales.csv')
print("All raw files downloaded successfully")

# ==============================
# LOAD DATASETS
# ==============================
customer_df = pd.read_csv('../raw_data/customer.csv')
product_df  = pd.read_csv('../raw_data/product.csv')
sales_df    = pd.read_csv('../raw_data/sales.csv')
print("Datasets Loaded Successfully")

# ==============================
# DATA CLEANING
# ==============================
customer_df = customer_df.dropna().drop_duplicates()
product_df  = product_df.dropna().drop_duplicates()
sales_df    = sales_df.dropna().drop_duplicates()
print("Data cleaned successfully")

# ==============================
# DATA TRANSFORMATION
# ==============================
merged_df = sales_df.copy()

if 'Product ID' in sales_df.columns and 'Product ID' in product_df.columns:
    merged_df = pd.merge(sales_df, product_df, on='Product ID', how='left')

if 'Quantity' in merged_df.columns and 'Sales' in merged_df.columns:
    merged_df['Total Revenue'] = merged_df['Quantity'] * merged_df['Sales']

print("Data transformation completed")

# ==============================
# SAVE FINAL FILE
# ==============================
final_file_name = '../processed_data/final_processed_data.csv'
merged_df.to_csv(final_file_name, index=False)
print("Processed CSV created")

# ==============================
# UPLOAD TO S3
# ==============================
s3.upload_file(final_file_name, bucket_name, processed_file_key)
print("Processed file uploaded to S3")

# ==============================
# GENERATE ANALYTICS DASHBOARD
# ==============================
print("Generating Analytics Dashboard...")

df = pd.read_csv(final_file_name)

# Detect column names flexibly
sales_col    = next((c for c in df.columns if 'sale'   in c.lower()), None)
profit_col   = next((c for c in df.columns if 'profit' in c.lower()), None)
qty_col      = next((c for c in df.columns if 'qty'    in c.lower() or 'quantity' in c.lower()), None)
order_col    = next((c for c in df.columns if 'order'  in c.lower() and 'id' in c.lower()), None)
cust_col     = next((c for c in df.columns if 'cust'   in c.lower()), None)
product_col  = next((c for c in df.columns if 'product' in c.lower() and 'id' in c.lower()), None)
date_col     = next((c for c in df.columns if 'order'  in c.lower() and 'date' in c.lower()), None)
ship_col     = next((c for c in df.columns if 'ship'   in c.lower() and 'mode' in c.lower()), None)

# KPIs
total_sales     = round(df[sales_col].sum(), 2)  if sales_col  else 0
total_profit    = round(df[profit_col].sum(), 2) if profit_col else 0
total_orders    = df[order_col].nunique()         if order_col  else len(df)
total_customers = df[cust_col].nunique()          if cust_col   else 0

# Monthly trend
if date_col and sales_col:
    df['_date'] = pd.to_datetime(df[date_col], errors='coerce')
    df['_month'] = df['_date'].dt.to_period('M').astype(str)
    monthly = df.groupby('_month')[sales_col].sum().sort_index().tail(12)
    monthly_labels = list(monthly.index)
    monthly_values = [round(v, 2) for v in monthly.values]
else:
    monthly_labels, monthly_values = [], []

# Category (from product ID prefix)
if product_col and sales_col:
    df['_cat'] = df[product_col].astype(str).str.split('-').str[0]
    cat = df.groupby('_cat')[sales_col].sum().sort_values(ascending=False)
    cat_labels = list(cat.index)
    cat_values = [round(v, 2) for v in cat.values]
else:
    cat_labels, cat_values = [], []

# Top 10 products
if product_col and sales_col:
    top10 = df.groupby(product_col)[sales_col].sum().sort_values(ascending=False).head(10)
    top10_labels = list(top10.index)
    top10_values = [round(v, 2) for v in top10.values]
else:
    top10_labels, top10_values = [], []

# Ship mode
if ship_col and sales_col:
    ship = df.groupby(ship_col)[sales_col].sum().sort_values(ascending=False)
    ship_labels = list(ship.index)
    ship_values = [round(v, 2) for v in ship.values]
else:
    ship_labels, ship_values = [], []

# Year over year
if date_col and sales_col:
    df['_year'] = df['_date'].dt.year
    yoy = df.groupby('_year')[sales_col].sum().sort_index()
    year_labels = [str(y) for y in yoy.index]
    year_values = [round(v, 2) for v in yoy.values]
else:
    year_labels, year_values = [], []

# Profit by category
if product_col and profit_col:
    profit_cat = df.groupby('_cat')[profit_col].sum().sort_values(ascending=False)
    pcat_labels = list(profit_cat.index)
    pcat_values = [round(v, 2) for v in profit_cat.values]
else:
    pcat_labels, pcat_values = [], []

def fmt(val):
    if val >= 1_000_000: return f"${val/1_000_000:.2f}M"
    if val >= 1_000:     return f"${val/1_000:.1f}K"
    return f"${val:,.0f}"

# Ship mode bar HTML
ship_max = ship_values[0] if ship_values else 1
ship_colors = ['#7c5cfc','#00d4aa','#ffd93d','#ff6b6b']
ship_rows_html = ""
for i, (lbl, val) in enumerate(zip(ship_labels, ship_values)):
    pct = round(val / ship_max * 100)
    color = ship_colors[i % len(ship_colors)]
    ship_rows_html += f"""
    <div class="ship-row">
      <div class="ship-dot" style="background:{color}"></div>
      <div class="ship-label">{lbl}</div>
      <div class="ship-bar-wrap">
        <div class="ship-bar" style="width:{pct}%;background:{color}"></div>
      </div>
      <div class="ship-val">{fmt(val)}</div>
    </div>"""

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E-Commerce Sales Analytics Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;700&display=swap');
  :root {{
    --bg:#0f1117; --surface:#1a1d27; --border:#2e3248;
    --accent:#7c5cfc; --accent2:#00d4aa; --accent3:#ff6b6b; --accent4:#ffd93d;
    --text:#e8eaf0; --muted:#8890a8;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; }}
  header {{ background:var(--surface); border-bottom:1px solid var(--border); padding:18px 32px; display:flex; align-items:center; justify-content:space-between; }}
  .logo {{ font-family:'Space Grotesk',sans-serif; font-size:20px; font-weight:700; }}
  .logo span {{ color:var(--accent); }}
  .badge {{ background:linear-gradient(135deg,#7c5cfc22,#00d4aa22); border:1px solid var(--accent); color:var(--accent); font-size:11px; font-weight:600; padding:4px 12px; border-radius:20px; letter-spacing:1px; text-transform:uppercase; }}
  .container {{ padding:28px 32px; max-width:1400px; margin:0 auto; }}
  .section-title {{ font-family:'Space Grotesk',sans-serif; font-size:13px; font-weight:500; color:var(--muted); letter-spacing:2px; text-transform:uppercase; margin-bottom:16px; margin-top:32px; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
  .kpi-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:24px 22px; position:relative; overflow:hidden; }}
  .kpi-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background:var(--ca,var(--accent)); border-radius:14px 14px 0 0; }}
  .kpi-label {{ font-size:11px; font-weight:600; letter-spacing:1.5px; text-transform:uppercase; color:var(--muted); margin-bottom:10px; }}
  .kpi-value {{ font-family:'Space Grotesk',sans-serif; font-size:32px; font-weight:700; line-height:1; margin-bottom:8px; }}
  .kpi-sub {{ font-size:12px; color:var(--accent2); font-weight:500; }}
  .charts-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-top:8px; }}
  .charts-grid-3 {{ display:grid; grid-template-columns:2fr 1fr; gap:20px; margin-top:8px; }}
  .chart-card {{ background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:24px; }}
  .chart-title {{ font-family:'Space Grotesk',sans-serif; font-size:15px; font-weight:600; margin-bottom:4px; }}
  .chart-sub {{ font-size:12px; color:var(--muted); margin-bottom:20px; }}
  canvas {{ max-height:240px; }}
  .ship-list {{ display:flex; flex-direction:column; gap:12px; margin-top:8px; }}
  .ship-row {{ display:flex; align-items:center; gap:12px; }}
  .ship-dot {{ width:10px; height:10px; border-radius:50%; flex-shrink:0; }}
  .ship-label {{ font-size:13px; flex:1; }}
  .ship-bar-wrap {{ width:120px; height:6px; background:var(--border); border-radius:4px; }}
  .ship-bar {{ height:6px; border-radius:4px; }}
  .ship-val {{ font-size:12px; color:var(--muted); min-width:70px; text-align:right; }}
  footer {{ text-align:center; padding:24px; color:var(--muted); font-size:12px; border-top:1px solid var(--border); margin-top:40px; }}
</style>
</head>
<body>
<header>
  <div class="logo">Ecom<span>Analytics</span></div>
  <div style="font-size:13px;color:var(--muted)">End-to-End Data Pipeline · AWS S3 + Python ETL</div>
  <div class="badge">Auto-Generated</div>
</header>
<div class="container">
  <div class="section-title">Key Performance Indicators</div>
  <div class="kpi-grid">
    <div class="kpi-card" style="--ca:#7c5cfc"><div class="kpi-label">Total Revenue</div><div class="kpi-value">{fmt(total_sales)}</div><div class="kpi-sub">All years combined</div></div>
    <div class="kpi-card" style="--ca:#00d4aa"><div class="kpi-label">Total Profit</div><div class="kpi-value">{fmt(total_profit)}</div><div class="kpi-sub">{round(total_profit/total_sales*100,1) if total_sales else 0}% profit margin</div></div>
    <div class="kpi-card" style="--ca:#ffd93d"><div class="kpi-label">Total Orders</div><div class="kpi-value">{total_orders:,}</div><div class="kpi-sub">Unique order IDs</div></div>
    <div class="kpi-card" style="--ca:#ff6b6b"><div class="kpi-label">Total Customers</div><div class="kpi-value">{total_customers:,}</div><div class="kpi-sub">Unique customer IDs</div></div>
  </div>
  <div class="section-title">Revenue Analysis</div>
  <div class="charts-grid">
    <div class="chart-card"><div class="chart-title">Monthly Sales Trend</div><div class="chart-sub">Last 12 months revenue</div><canvas id="monthlyChart"></canvas></div>
    <div class="chart-card"><div class="chart-title">Sales by Category</div><div class="chart-sub">Product line breakdown</div><canvas id="categoryChart"></canvas></div>
  </div>
  <div class="section-title">Product & Fulfillment Insights</div>
  <div class="charts-grid-3">
    <div class="chart-card"><div class="chart-title">Top 10 Products by Revenue</div><div class="chart-sub">Highest-grossing SKUs</div><canvas id="topProductsChart"></canvas></div>
    <div class="chart-card"><div class="chart-title">Sales by Ship Mode</div><div class="chart-sub">Fulfillment breakdown</div><div class="ship-list">{ship_rows_html}</div></div>
  </div>
  <div class="section-title">Year-over-Year Growth</div>
  <div class="charts-grid">
    <div class="chart-card"><div class="chart-title">Annual Revenue Growth</div><div class="chart-sub">Year-over-year comparison</div><canvas id="yearChart"></canvas></div>
    <div class="chart-card"><div class="chart-title">Profit by Category</div><div class="chart-sub">Net profit per product line</div><canvas id="profitChart"></canvas></div>
  </div>
</div>
<footer>End-to-End Data Pipeline for E-commerce & Sales Analytics &nbsp;·&nbsp; AWS S3 → Python ETL (Pandas + Boto3) → Analytics Dashboard &nbsp;·&nbsp; {len(df):,} records processed</footer>
<script>
Chart.defaults.color='#8890a8'; Chart.defaults.borderColor='#2e3248'; Chart.defaults.font.family='Inter';
const a='#7c5cfc',a2='#00d4aa',a3='#ff6b6b',a4='#ffd93d';

new Chart(document.getElementById('monthlyChart'),{{
  type:'line',
  data:{{ labels:{monthly_labels}, datasets:[{{ label:'Revenue', data:{monthly_values}, borderColor:a, backgroundColor:a+'20', fill:true, tension:0.4, pointBackgroundColor:a, pointRadius:4 }}] }},
  options:{{ responsive:true, plugins:{{ legend:{{ display:false }} }}, scales:{{ y:{{ ticks:{{ callback:v=>'$'+(v/1000).toFixed(0)+'K' }} }}, x:{{ grid:{{ display:false }} }} }} }}
}});

new Chart(document.getElementById('categoryChart'),{{
  type:'doughnut',
  data:{{ labels:{cat_labels}, datasets:[{{ data:{cat_values}, backgroundColor:[a,a2,a4,a3], borderColor:'#1a1d27', borderWidth:3, hoverOffset:8 }}] }},
  options:{{ responsive:true, cutout:'65%', plugins:{{ legend:{{ position:'bottom', labels:{{ padding:16, boxWidth:12 }} }}, tooltip:{{ callbacks:{{ label:ctx=>' $'+(ctx.raw/1000).toFixed(1)+'K' }} }} }} }}
}});

new Chart(document.getElementById('topProductsChart'),{{
  type:'bar',
  data:{{ labels:{top10_labels}, datasets:[{{ label:'Sales', data:{top10_values}, backgroundColor:[a+'dd',a2+'dd',a4+'dd',a3+'dd',a+'aa',a2+'aa',a4+'aa',a3+'aa',a+'88',a2+'88'], borderRadius:6, borderSkipped:false }}] }},
  options:{{ indexAxis:'y', responsive:true, plugins:{{ legend:{{ display:false }} }}, scales:{{ x:{{ ticks:{{ callback:v=>'$'+(v/1000).toFixed(0)+'K' }} }}, y:{{ grid:{{ display:false }}, ticks:{{ font:{{ size:11 }} }} }} }} }}
}});

new Chart(document.getElementById('yearChart'),{{
  type:'bar',
  data:{{ labels:{year_labels}, datasets:[{{ label:'Revenue', data:{year_values}, backgroundColor:[a+'55',a+'77',a+'99',a], borderRadius:8, borderSkipped:false }}] }},
  options:{{ responsive:true, plugins:{{ legend:{{ display:false }} }}, scales:{{ y:{{ ticks:{{ callback:v=>'$'+(v/1000).toFixed(0)+'K' }} }}, x:{{ grid:{{ display:false }} }} }} }}
}});

new Chart(document.getElementById('profitChart'),{{
  type:'bar',
  data:{{ labels:{pcat_labels}, datasets:[{{ label:'Profit', data:{pcat_values}, backgroundColor:[a,a2,a4,a3], borderRadius:8, borderSkipped:false }}] }},
  options:{{ responsive:true, plugins:{{ legend:{{ display:false }} }}, scales:{{ y:{{ ticks:{{ callback:v=>'$'+(v/1000).toFixed(0)+'K' }} }}, x:{{ grid:{{ display:false }} }} }} }}
}});
</script>
</body>
</html>"""

dashboard_path = '../processed_data/dashboard.html'
with open(dashboard_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
print("Dashboard HTML generated successfully")

# Upload dashboard to S3
s3.upload_file(dashboard_path, bucket_name, dashboard_file_key)
print("Dashboard uploaded to S3")

# ==============================
# PIPELINE COMPLETED
# ==============================
print("ETL Pipeline Completed Successfully")