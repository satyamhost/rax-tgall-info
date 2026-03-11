from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# ===== BRANDING =====
NAME = "SATYAM"
COPYRIGHT = "@TEAMRAX0"
OWNER = "@TEAMRAX0"
CHANNEL = "@Allaboutrax"
API_NAME = "RAX ULTRA PRO TG INFO API"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}

TIMEOUT = 15


def clean_text(text):
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip()


def extract_style_url(style_text):
    if not style_text:
        return None
    match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_text)
    return match.group(1) if match else None


def detect_page_type(username, extra_text, action_text, description):
    uname = (username or "").lower()
    extra_low = (extra_text or "").lower()
    action_low = (action_text or "").lower()
    desc_low = (description or "").lower()

    if uname.endswith("bot") or "send message" in action_low or "bot" in desc_low:
        return "bot"

    if "subscriber" in extra_low:
        return "channel"

    if "member" in extra_low:
        return "group"

    return "user_or_unknown"


def parse_member_count(extra_text):
    if not extra_text:
        return None
    return extra_text


def extract_main_page(username):
    url = f"https://t.me/{username}"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

    result = {
        "status_code": r.status_code,
        "page_url": url,
        "html": None,
        "soup": None
    }

    if r.status_code != 200:
        return result

    result["html"] = r.text
    result["soup"] = BeautifulSoup(r.text, "lxml")
    return result


def extract_profile_info(username, soup, html):
    title_tag = soup.select_one(".tgme_page_title")
    desc_tag = soup.select_one(".tgme_page_description")
    extra_tag = soup.select_one(".tgme_page_extra")
    action_tag = soup.select_one(".tgme_page_action .tgme_action_button_new, .tgme_page_action .tgme_action_button")
    photo_tag = soup.select_one(".tgme_page_photo_image")
    context_wrap = soup.select_one(".tgme_page_context_link_wrap a")

    title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None
    description = clean_text(desc_tag.get_text(" ", strip=True)) if desc_tag else None
    extra_text = clean_text(extra_tag.get_text(" ", strip=True)) if extra_tag else None
    action_text = clean_text(action_tag.get_text(" ", strip=True)) if action_tag else None

    profile_photo = None
    if photo_tag and photo_tag.get("style"):
        profile_photo = extract_style_url(photo_tag.get("style"))

    if not profile_photo:
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            profile_photo = og_image.get("content")

    verified = False
    if "verified-icon" in html.lower():
        verified = True

    action_button_url = None
    if action_tag and action_tag.get("href"):
        action_button_url = action_tag.get("href")

    context_link = context_wrap.get("href") if context_wrap and context_wrap.get("href") else None

    page_type = detect_page_type(username, extra_text, action_text, description)

    return {
        "title": title,
        "about": description,
        "extra_text": extra_text,
        "members_or_subscribers": parse_member_count(extra_text),
        "action_button": action_text,
        "action_button_url": action_button_url,
        "context_link": context_link,
        "profile_photo": profile_photo,
        "verified": verified,
        "page_type": page_type,
        "is_bot_guess": page_type == "bot",
        "is_channel_guess": page_type == "channel",
        "is_group_guess": page_type == "group",
        "has_description": description is not None,
        "has_profile_photo": profile_photo is not None
    }


def extract_recent_post_info(username):
    s_url = f"https://t.me/s/{username}"

    try:
        r = requests.get(s_url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        return {
            "has_recent_posts": False,
            "estimated_recent_post_count": 0,
            "latest_post_link": None,
            "latest_post_date": None,
            "latest_post_views": None,
            "latest_post_text": None,
            "latest_post_has_media": False,
            "latest_post_media_type": None
        }

    if r.status_code != 200:
        return {
            "has_recent_posts": False,
            "estimated_recent_post_count": 0,
            "latest_post_link": None,
            "latest_post_date": None,
            "latest_post_views": None,
            "latest_post_text": None,
            "latest_post_has_media": False,
            "latest_post_media_type": None
        }

    soup = BeautifulSoup(r.text, "lxml")
    posts = soup.select(".tgme_widget_message_wrap")

    if not posts:
        return {
            "has_recent_posts": False,
            "estimated_recent_post_count": 0,
            "latest_post_link": None,
            "latest_post_date": None,
            "latest_post_views": None,
            "latest_post_text": None,
            "latest_post_has_media": False,
            "latest_post_media_type": None
        }

    last_post = posts[-1]

    date_link = last_post.select_one(".tgme_widget_message_date")
    latest_post_link = date_link.get("href") if date_link and date_link.get("href") else None

    time_tag = date_link.find("time") if date_link else None
    latest_post_date = time_tag.get("datetime") if time_tag and time_tag.get("datetime") else None

    views_tag = last_post.select_one(".tgme_widget_message_views")
    latest_post_views = clean_text(views_tag.get_text(" ", strip=True)) if views_tag else None

    text_tag = last_post.select_one(".tgme_widget_message_text")
    latest_post_text = clean_text(text_tag.get_text(" ", strip=True)) if text_tag else None
    if latest_post_text and len(latest_post_text) > 300:
        latest_post_text = latest_post_text[:300] + "..."

    media_type = None
    has_media = False

    if last_post.select_one(".tgme_widget_message_photo_wrap"):
        has_media = True
        media_type = "photo"
    elif last_post.select_one(".tgme_widget_message_video"):
        has_media = True
        media_type = "video"
    elif last_post.select_one(".tgme_widget_message_document"):
        has_media = True
        media_type = "document"
    elif last_post.select_one(".tgme_widget_message_animation"):
        has_media = True
        media_type = "animation"

    return {
        "has_recent_posts": True,
        "estimated_recent_post_count": len(posts),
        "latest_post_link": latest_post_link,
        "latest_post_date": latest_post_date,
        "latest_post_views": latest_post_views,
        "latest_post_text": latest_post_text,
        "latest_post_has_media": has_media,
        "latest_post_media_type": media_type
    }


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "api_name": API_NAME,
        "developer_name": NAME,
        "copyright": COPYRIGHT,
        "ownership": OWNER,
        "channel": CHANNEL,
        "endpoint": "/tginfo?username=telegram",
        "fields_count": "20+"
    })


@app.route("/health")
def health():
    return jsonify({
        "success": True,
        "service": API_NAME,
        "status": "running",
        "developer_name": NAME,
        "copyright": COPYRIGHT,
        "ownership": OWNER,
        "channel": CHANNEL
    })


@app.route("/tginfo", methods=["GET"])
def tginfo():
    username = request.args.get("username", "").strip().replace("@", "")

    if not username:
        return jsonify({
            "success": False,
            "message": "username parameter required",
            "example": "/tginfo?username=telegram",
            "developer_name": NAME,
            "copyright": COPYRIGHT,
            "ownership": OWNER,
            "channel": CHANNEL
        }), 400

    try:
        page_data = extract_main_page(username)

        if page_data["status_code"] != 200 or not page_data["soup"]:
            return jsonify({
                "success": False,
                "developer_name": NAME,
                "copyright": COPYRIGHT,
                "ownership": OWNER,
                "channel": CHANNEL,
                "source": "telegram_public_page",
                "message": "username not found or page unavailable",
                "input": username,
                "status_code": page_data["status_code"]
            }), 404

        profile_info = extract_profile_info(username, page_data["soup"], page_data["html"])
        post_info = extract_recent_post_info(username)

        result = {
            "input": username,
            "username": username,
            "title": profile_info["title"],
            "about": profile_info["about"],
            "page_type": profile_info["page_type"],
            "verified": profile_info["verified"],
            "is_bot_guess": profile_info["is_bot_guess"],
            "is_channel_guess": profile_info["is_channel_guess"],
            "is_group_guess": profile_info["is_group_guess"],
            "profile_photo": profile_info["profile_photo"],
            "page_url": page_data["page_url"],
            "public_link": f"https://t.me/{username}",
            "extra_text": profile_info["extra_text"],
            "members_or_subscribers": profile_info["members_or_subscribers"],
            "action_button": profile_info["action_button"],
            "action_button_url": profile_info["action_button_url"],
            "context_link": profile_info["context_link"],
            "has_description": profile_info["has_description"],
            "has_profile_photo": profile_info["has_profile_photo"],
            "has_recent_posts": post_info["has_recent_posts"],
            "estimated_recent_post_count": post_info["estimated_recent_post_count"],
            "latest_post_link": post_info["latest_post_link"],
            "latest_post_date": post_info["latest_post_date"],
            "latest_post_views": post_info["latest_post_views"],
            "latest_post_text": post_info["latest_post_text"],
            "latest_post_has_media": post_info["latest_post_has_media"],
            "latest_post_media_type": post_info["latest_post_media_type"],
            "status_code": page_data["status_code"]
        }

        return jsonify({
            "success": True,
            "api_name": API_NAME,
            "developer_name": NAME,
            "copyright": COPYRIGHT,
            "ownership": OWNER,
            "channel": CHANNEL,
            "source": "telegram_public_page",
            "note": "Only public Telegram data is returned. Private account data and hidden internal IDs are not available from public scraping.",
            "data": result
        })

    except requests.RequestException as e:
        return jsonify({
            "success": False,
            "developer_name": NAME,
            "copyright": COPYRIGHT,
            "ownership": OWNER,
            "channel": CHANNEL,
            "message": "request failed",
            "error": str(e)
        }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "developer_name": NAME,
            "copyright": COPYRIGHT,
            "ownership": OWNER,
            "channel": CHANNEL,
            "message": "internal server error",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
