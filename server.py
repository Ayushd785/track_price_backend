from flask import Flask, request, jsonify
import requests
import re
import os
import boto3
from datetime import datetime
from bs4 import BeautifulSoup
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS

# Scraper API Key

# Load AWS credentials from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")  # Default region
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")
# Initialize DynamoDB connection
dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

amazon_products_table = dynamodb.Table("AmazonProducts")
user_products_table = dynamodb.Table("UserProducts")

@app.route("/track", methods=["POST"])
def track_product():
    print("update1")
    print("Received request for product tracking")
    
    data = request.json
    product_url = data.get("productUrl")
    email = data.get("email")
    
    if not product_url or not email:
        return jsonify({"error": "Missing productUrl or email"}), 400

    # Extract Product ID from Amazon URL
    ID_match = re.search(r"/dp/([A-Z0-9]{10})", product_url)
    if not ID_match:
        return jsonify({"error": "Invalid Amazon URL"}), 400
    
    product_id = ID_match.group(1)
    scraper_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url=https://www.amazon.in/dp/{product_id}"

    try:
        response = requests.get(scraper_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.select_one("span#productTitle")
    title_text = title.text.strip() if title else "Title not found"
    
    price = soup.select_one("span.a-price-whole")
    if price:
        price_value = price.text.strip().replace(",", "")
    else:
        price = soup.select_one("span.a-offscreen")
        price_value = price.text.strip().replace("₹", "").replace(",", "") if price else "Price not found"

    product_info = {
        "ProductID": product_id,
        "price": price_value,
        "url": product_url,
        "title": title_text,
        "timestamp": datetime.now().isoformat(),
        "email": email,
    }

    # Store in AmazonProducts Table
    try:
        amazon_products_table.put_item(Item=product_info)
    except Exception as e:
        return jsonify({"error": "Failed to store product data", "details": str(e)}), 500

    # Store in UserProducts Table
    try:
        user_products_table.put_item(Item={
            "chat_id": email,
            "product_id": product_id,
            "stored_price": price_value,
        })
    except Exception as e:
        return jsonify({"error": "Failed to store user tracking info", "details": str(e)}), 500

    return jsonify({"message": "Tracking started successfully", "product": product_info})


if __name__ == "__main__":
    app.run(debug=True , host = '0.0.0.0' , port = 9000 )