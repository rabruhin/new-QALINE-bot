from flask import Flask, request, abort, jsonify
import threading
import os
import traceback

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

from azure.core.credentials import AzureKeyCredential
from azure.ai.language.questionanswering import QuestionAnsweringClient

# 初始化 Flask 應用
app = Flask(__name__)

# Channel Access Token 和 Channel Secret
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# Azure 認證和設定
endpoint = os.getenv('END_POINT')
credential = AzureKeyCredential(os.getenv('AZURE_KEY'))
knowledge_base_project = os.getenv('PROJECT')
deployment = 'production'

def QA_response(text):
    client = QuestionAnsweringClient(endpoint, credential)
    with client:
        question = text
        output = client.get_answers(
            question=question,
            project_name=knowledge_base_project,
            deployment_name=deployment
        )
    return output.answers[0].answer

@app.route("/callback", methods=['POST'])
def callback():
    # 獲取 X-Line-Signature header 值
    signature = request.headers['X-Line-Signature']
    # 獲取請求體
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # 處理 webhook 請求
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    if msg[0] != '-':
        # 立即回應 Line 伺服器
        response = jsonify({"status": "received"})
        response.status_code = 200
        
        # 在後台執行長時間處理任務
        threading.Thread(target=process_message, args=(event,)).start()
        
        return response

def process_message(event):
    msg = event.message.text
    try:
        QA_answer = QA_response(msg)
        print(QA_answer)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(QA_answer))
    except:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage('QA Error'))

@handler.add(PostbackEvent)
def handle_postback(event):
    print(event.postback.data)

@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name} 歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
