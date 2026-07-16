from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import numpy as np
import joblib
import os
import psycopg2
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus import TableStyle
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ================= DATABASE =================

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_log(
            id SERIAL PRIMARY KEY,
            material_name TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


init_db()

# ================= LOAD DATA =================

df = pd.read_csv("dataset/EcoPackAI_materials.csv")

rf_cost = joblib.load("models/rf_cost.pkl")
xgb_co2 = joblib.load("models/xgb_co2.pkl")
scaler = joblib.load("models/scaler.pkl")
# ================= BASELINE VALUES =================

baseline_co2 = df["co2_score"].mean()
baseline_cost = df["cost"].mean()

last_full_ranking = []
last_top5 = []

# ================= FILTER =================


def apply_filters(data, category, fragility):

    filtered = data.copy()

    if fragility == "medium":
        filtered = filtered[filtered["strength"] >= 2]

    elif fragility == "high":
        filtered = filtered[filtered["strength"] == 3]

    if category == "electronics":
        filtered = filtered[filtered["strength"] >= 2]

    elif category == "food":
        filtered = filtered[
            filtered["biodegradability_score"] >= 2
        ]

    elif category == "cosmetics":
        filtered = filtered[
            filtered["recyclability_percent"] >= 40
        ]

    return filtered


# ================= WEIGHTS =================

def get_weights(shipping, sustainability):

    cost_w = 0.4
    co2_w = 0.4
    suit_w = 0.2

    if shipping == "international":
        co2_w = 0.5
        cost_w = 0.3

    if sustainability == "high":
        co2_w = 0.5
        suit_w = 0.3
        cost_w = 0.2

    return cost_w, co2_w, suit_w


# ================= HOME =================

@app.route("/")
def home():
    return render_template("index.html")


# ================= RECOMMEND =================

@app.route("/recommend", methods=["POST"])
def recommend():

    global last_full_ranking
    global last_top5

    data = request.json

    filtered_df = apply_filters(
        df,
        data["category"],
        data["fragility"]
    )

    cost_w, co2_w, suit_w = get_weights(
        data["shipping"],
        data["sustainability"]
    )

    results = []

    for _, row in filtered_df.iterrows():

        features = np.array([[
    row["strength"],
    row["weight_capacity"],
    row["biodegradability_score"],
    row["recyclability_percent"]
]], dtype=float)

        predicted_cost = float(
            rf_cost.predict(features)[0]
        )

        predicted_co2 = max(
    0,
    float(
        xgb_co2.predict(
            scaler.transform(features)
        )[0]
    )
)

        suitability = (
            0.4 * row["strength"] +
            0.3 * row["recyclability_percent"] +
            0.3 * row["biodegradability_score"]
        )

        final_score = (
            cost_w * predicted_cost +
            co2_w * predicted_co2 +
            suit_w * suitability
        )

        co2_reduction = max(
    0,
    ((baseline_co2 - predicted_co2) / baseline_co2) * 100
)

        cost_saving = baseline_cost - predicted_cost

        results.append({
            "material": str(row["material_name"]),
            "predicted_cost": round(predicted_cost, 2),
            "predicted_co2": round(predicted_co2, 2),
            "co2_reduction_percent": round(co2_reduction, 2),
            "cost_saving": round(cost_saving, 2),
            "final_score": round(final_score, 2)
        })

    results = sorted(
        results,
        key=lambda x: x["final_score"]
    )

    last_full_ranking = results
    last_top5 = results[:5]

    conn = get_db_connection()
    cursor = conn.cursor()

    for item in last_top5:

        cursor.execute(
            "INSERT INTO usage_log(material_name) VALUES(%s)",
            (item["material"],)
        )

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify(results[:5])


# ================= USAGE =================

@app.route("/usage")
def usage():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT material_name,
               COUNT(*)
        FROM usage_log
        GROUP BY material_name
    """)

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(
        {row[0]: row[1] for row in data}
    )


# ================= EXPORT EXCEL =================

@app.route("/export_excel")
def export_excel():

    if not last_full_ranking:
        return "No recommendations available"

    df_export = pd.DataFrame(last_full_ranking)

    file_path = "full_ranking.xlsx"

    df_export.to_excel(file_path, index=True)

    return send_file(
        file_path,
        as_attachment=True
    )


# ================= EXPORT PDF =================

@app.route("/export_pdf")
def export_pdf():

    if not last_top5:
        return "No recommendations available"

    file_path = "EcoPackAI_Recommendations.pdf"

    doc = SimpleDocTemplate(file_path)

    elements = []

    styles = getSampleStyleSheet()

    elements.append(
        Paragraph(
            "<b>EcoPackAI - Recommended Materials</b>",
            styles["Title"]
        )
    )

    elements.append(Spacer(1, 15))

    table_data = [[
        "Rank",
        "Material",
        "Predicted Cost",
        "Predicted CO2",
        "CO2 Reduction",
        "Cost Saving"
    ]]

    for index, item in enumerate(last_top5, start=1):

        table_data.append([
            index,
            item["material"],
            item["predicted_cost"],
            item["predicted_co2"],
            f'{item["co2_reduction_percent"]}%',
            item["cost_saving"]
        ])

    table = Table(table_data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#198754")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 1), (-1, -1), "CENTER")
    ]))

    elements.append(table)

    doc.build(elements)

    return send_file(
        file_path,
        as_attachment=True
    )


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)