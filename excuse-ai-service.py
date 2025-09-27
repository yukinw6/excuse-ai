import json
import os
from datetime import datetime
from flask import Flask, request
from google.cloud import storage, firestore
import vertexai
from base64 import b64decode

app = Flask(__name__)

# GCP clients
PROJECT_ID = os.getenv('PROJECT_ID')
LOCATION = os.getenv('LOCATION', 'asia-northeast1')

storage_client = storage.Client()
db = firestore.Client()

# Vertex AI初期化
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Frontend HTML content embedded in the Python file
# NOTE: Replace 'YOUR-CLOUD-RUN-SERVICE-URL' and 'YOUR-CLOUD-STORAGE-BUCKET' with your actual values.
# フロントエンドのHTMLコンテンツをPythonファイル内に埋め込み
# 注: 'YOUR-CLOUD-RUN-SERVICE-URL' と 'YOUR-CLOUD-STORAGE-BUCKET' を実際の値に置き換えてください。
FRONTEND_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>言い訳AI</title>
    <!-- Tailwind CSS を CDN 経由で読み込み -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Firebase を CDN 経由で読み込み -->
    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore-compat.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        .loading-animation {
            border-top-color: #3b82f6;
            -webkit-animation: spinner 1.5s linear infinite;
            animation: spinner 1.5s linear infinite;
        }
        @-webkit-keyframes spinner {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @keyframes spinner {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">

    <div class="bg-white p-8 rounded-xl shadow-lg w-full max-w-2xl">
        <h1 class="text-3xl font-bold text-gray-800 mb-6 text-center">言い訳AI</h1>
        <p class="text-gray-600 mb-8 text-center">障害情報を入力して、Geminiが生成する4段階の「言い訳」をゲットしよう。</p>

        <form id="excuseForm" class="space-y-6">
            <div>
                <label for="system_name" class="block text-sm font-medium text-gray-700">システム名</label>
                <input type="text" id="system_name" name="system_name" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label for="failure_type" class="block text-sm font-medium text-gray-700">障害内容</label>
                <input type="text" id="failure_type" name="failure_type" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label for="occurred_at" class="block text-sm font-medium text-gray-700">発生日時</label>
                <input type="datetime-local" id="occurred_at" name="occurred_at" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label for="detected_at" class="block text-sm font-medium text-gray-700">検知日時</label>
                <input type="datetime-local" id="detected_at" name="detected_at" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div>
                <label for="impact" class="block text-sm font-medium text-gray-700">影響度</label>
                <select id="impact" name="impact" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                    <option value="低">低</option>
                    <option value="中">中</option>
                    <option value="高">高</option>
                </select>
            </div>
            
            <button type="submit" id="submitBtn" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                言い訳を生成
            </button>
        </form>

        <div id="loading" class="hidden flex items-center justify-center mt-8">
            <div class="loading-animation w-8 h-8 rounded-full border-4 border-gray-200"></div>
            <p class="ml-3 text-gray-600">言い訳を生成中...</p>
        </div>

        <div id="results" class="hidden mt-8 space-y-4">
            <!-- 結果がここに動的に挿入されます -->
        </div>

        <div id="error" class="hidden mt-8 text-red-600 text-center font-bold">
            <!-- エラーメッセージがここに表示されます -->
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const form = document.getElementById('excuseForm');
            const submitBtn = document.getElementById('submitBtn');
            const loadingDiv = document.getElementById('loading');
            const resultsDiv = document.getElementById('results');
            const errorDiv = document.getElementById('error');
            
            // FIXME: 以下のURLをあなたのCloud RunサービスURLに置き換えてください。
            // 例えば、https://excuse-ai-service-frs7ty7nla-an.a.run.app のような形式です。
            const API_ENDPOINT = window.location.origin + '/';
            
            // FIXME: Firebaseの設定オブジェクトに置き換えてください。
            const firebaseConfig = {
            apiKey: "AIzaSyC-5fClZcJwvwTnGg70ps7Uk5oWg2Bfq5E",
            authDomain: "scenic-parity-465008-n7.firebaseapp.com",
            projectId: "scenic-parity-465008-n7",
            storageBucket: "scenic-parity-465008-n7.firebasestorage.app",
            messagingSenderId: "870325242719",
            appId: "1:870325242719:web:797f8345e40be5bf7944ea"
            };

            // Firebase初期化
            const app = firebase.initializeApp(firebaseConfig);
            const db = firebase.firestore();

            const dayOfWeek = (dateString) => {
                const days = ['日', '月', '火', '水', '木', '金', '土'];
                const date = new Date(dateString);
                return days[date.getDay()];
            };
            
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                // UIの状態をリセット
                resultsDiv.classList.add('hidden');
                errorDiv.classList.add('hidden');
                submitBtn.disabled = true;
                submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
                loadingDiv.classList.remove('hidden');
                
                const incidentId = 'WEB-REQ-' + Date.now();
                const occurredAt = document.getElementById('occurred_at').value;
                const detectedAt = document.getElementById('detected_at').value;
                
                const payload = {
                    message: {
                        attributes: {
                            incidentId: incidentId // 新しく追加
                        },
                        data: btoa(JSON.stringify({
                            incident_id: incidentId,
                            system_name: document.getElementById('system_name').value,
                            failure_type: document.getElementById('failure_type').value,
                            occurred_at: occurredAt,
                            detected_at: detectedAt,
                            day_of_week: dayOfWeek(occurredAt),
                            impact: document.getElementById('impact').value,
                        }))
                    }
                };
                
                // Firestoreのドキュメントを監視
                const docRef = db.collection('excuses').doc(incidentId);
                const unsubscribe = docRef.onSnapshot((doc) => {
                    if (doc.exists) {
                        const result = doc.data();
                        displayResults(result);
                        unsubscribe(); // データ取得後、リスナーを停止
                    }
                });

                try {
                    const response = await fetch(API_ENDPOINT, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(payload)
                    });
                    
                    if (!response.ok) {
                        throw new Error(`API呼び出しに失敗しました: ${response.status} ${response.statusText}`);
                    }
                    
                } catch (err) {
                    displayError(err.message);
                    unsubscribe(); // エラー発生時もリスナーを停止
                }
            });

            // 結果を整形して表示する関数
            const displayResults = (data) => {
                loadingDiv.classList.add('hidden');
                submitBtn.disabled = false;
                submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                resultsDiv.classList.remove('hidden');
                
                const excuses = data.excuses;
                const difficulty = data.difficulty_score;

                let html = `
                    <div class="text-center mb-4">
                        <span class="text-lg font-bold">難易度スコア: ${difficulty}/100</span>
                    </div>
                `;

                const levels = {
                    "level1": "正当な理由",
                    "level2": "ギリギリの言い訳",
                    "level3": "無理がある言い訳",
                    "level4": "完全にネタ"
                };

                for (const key in excuses) {
                    if (excuses.hasOwnProperty(key)) {
                        html += `
                            <div class="bg-gray-50 p-4 rounded-lg shadow-sm">
                                <h3 class="font-semibold text-gray-800 mb-2">${levels[key]}</h3>
                                <p class="text-gray-700">${excuses[key]}</p>
                            </div>
                        `;
                    }
                }
                resultsDiv.innerHTML = html;
            };

            const displayError = (message) => {
                loadingDiv.classList.add('hidden');
                submitBtn.disabled = false;
                submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                errorDiv.classList.remove('hidden');
                errorDiv.textContent = `エラー: ${message}`;
            };
        });
    </script>
</body>
</html>
"""

def generate_excuses(incident_data):
    """Geminiで言い訳を生成"""
    
    # 遅延時間計算
    occurred = datetime.fromisoformat(incident_data['occurred_at'])
    detected = datetime.fromisoformat(incident_data['detected_at'])
    delay_hours = (detected - occurred).total_seconds() / 3600
    
    prompt = f"""あなたはシステム運用エンジニアです。以下の障害について、4段階の「言い訳」を生成してください。
各レベルは次の特徴を持ちます：

障害情報：
- システム: {incident_data['system_name']}
- 内容: {incident_data['failure_type']}
- 発生: {incident_data['occurred_at']} ({incident_data['day_of_week']})
- 検知: {incident_data['detected_at']}
- 遅延: {delay_hours:.1f}時間
- 影響度: {incident_data['impact']}

レベル1（正当な理由）: 実際に報告書で使える、プロフェッショナルで説得力のある説明
レベル2（ギリギリ）: 少し苦しいが理解される可能性がある説明
レベル3（無理がある）: 明らかに説得力に欠けるが一応言い訳になっている
レベル4（完全にネタ）: 笑えるジョーク的な言い訳

以下のJSON形式で出力してください：
{{
  "level1": "正当な理由の文章",
  "level2": "ギリギリの言い訳文章",
  "level3": "無理がある言い訳文章",
  "level4": "ネタ的な言い訳文章"
}}
"""

    try:
        # Vertex AI Generative AI Studio経由でGemini呼び出し
        print("Attempting to call Gemini...")
        from vertexai.preview.generative_models import GenerativeModel
        model = GenerativeModel("gemini-1.5-flash-002")
        print("Model created successfully")
        
        response = model.generate_content(prompt)
        print(f"Gemini response received")
        llm_output = response.text
        
        print(f"Gemini raw response: {llm_output[:500]}...")  # デバッグ用
        
        # JSON抽出（```jsonブロックがある場合に対応）
        if "```json" in llm_output:
            llm_output = llm_output.split("```json")[1].split("```")[0].strip()
        elif "```" in llm_output:
            llm_output = llm_output.split("```")[1].split("```")[0].strip()
        
        excuses = json.loads(llm_output)
        
    except Exception as e:
        print(f"Error generating excuses: {e}")
        print(f"Exception type: {type(e)}")
        print(f"Raw LLM output: {llm_output if 'llm_output' in locals() else 'No output'}")
        # エラー時のフォールバック
        excuses = {
            "level1": f"監視システムの通知設定に盲点があり、{delay_hours:.1f}時間の検知遅延が発生しました。設定の見直しを実施します。",
            "level2": f"週末の体制移行時に引き継ぎが不十分で、月曜朝まで気づけませんでした。",
            "level3": f"実は早期に気づいていましたが、影響範囲の調査を優先していました。",
            "level4": f"{delay_hours:.0f}時間？それは時間の相対性理論的には一瞬です。アインシュタインも言ってました（多分）。"
        }
    
    return {
        "incident_id": incident_data['incident_id'],
        "delay_hours": delay_hours,
        "difficulty_score": min(100, int(delay_hours * 2 + (50 if incident_data['impact'] == '高' else 20))),
        "excuses": excuses,
        "generated_at": datetime.now().isoformat()
    }

@app.route('/pubsub', methods=['POST'])
def pubsub_push():
    print('[HIT] POST /pubsub → delegate to /')
    return root()

@app.route('/', methods=['GET', 'POST'])
def root():
    # ---------------------------
    # GET: ブラウザアクセス用（フロントのHTMLを返すだけ）
    # ---------------------------
    if request.method == 'GET':
        return FRONTEND_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}

    # ---------------------------
    # POST: Pub/Sub push または フロント直POST用
    # ---------------------------
    # JSONとしてリクエストボディを読み込む
    # 失敗したら None → or {} で空dictを代わりに入れる
    envelope = request.get_json(silent=True) or {}

    # Pub/Sub標準形式では "message" が入っている
    pubsub_message = envelope.get('message', {}) or {}
    attributes = pubsub_message.get('attributes', {}) or {}

    # ---------------------------
    # 1) dataフィールド（Base64エンコードされたJSON）を優先的に読む
    # フロントからの直POSTはこちらに必ず入っている想定
    # ---------------------------
    incident_data = None
    raw = pubsub_message.get('data')
    if raw:
        try:
            # Base64デコード → UTF-8文字列化 → JSONに変換
            incident_data = json.loads(b64decode(raw).decode('utf-8'))
        except Exception as e:
            print(f"[WARN] dataフィールドのデコード失敗: {e}")

    # ---------------------------
    # 2) dataが無い/壊れている場合のみ GCSオブジェクトを読む
    # （Eventarc/GCS通知経由のケースをカバー）
    # ---------------------------
    bucket_name = attributes.get('bucketId')
    object_id   = attributes.get('objectId')
    used_gcs_input = False
    if incident_data is None:
        if not bucket_name or not object_id:
            # 処理できるデータが無い場合 → ACKして再試行抑止
            return 'No actionable payload', 200

        print(f"[INFO] GCSから入力を読む: gs://{bucket_name}/{object_id}")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_id)
        if not blob.exists():
            # ファイルがもう無ければ既に処理済みとみなす → ACK
            return f'Input not found (treated as processed): gs://{bucket_name}/{object_id}', 200

        try:
            incident_data = json.loads(blob.download_as_text())
            used_gcs_input = True
        except Exception as e:
            print(f"[ERROR] GCSからの読み込み失敗: {e}")
            # ここでエラーを返しても再試行して直る見込みが薄いのでACK
            return 'Invalid input object', 200

    # ---------------------------
    # 3) incident_id の確保
    # attributesに入っていれば補完、最終的に必須
    # ---------------------------
    incident_id_attr = attributes.get('incidentId')
    if incident_id_attr and not incident_data.get('incident_id'):
        incident_data['incident_id'] = incident_id_attr

    if not incident_data.get('incident_id'):
        # 必須キーが無い場合はスキップ（ACKで握りつぶす）
        return 'incident_id missing, skipped', 200

    inc_id = incident_data['incident_id']

    # ---------------------------
    # 4) 冪等性チェック
    # Firestoreに既に同じincident_idがあれば処理済み → ACK
    # ---------------------------
    doc_ref = db.collection('excuses').document(inc_id)
    if doc_ref.get().exists:
        print(f"[INFO] 既に処理済み: {inc_id}")
        return 'Already processed', 200

    # ---------------------------
    # 5) Geminiで言い訳生成
    # generate_excuses内でフォールバック処理済み
    # ---------------------------
    try:
        result = generate_excuses(incident_data)
    except Exception as e:
        print(f"[ERROR] 言い訳生成に失敗: {e}")
        # 再試行させたいなら 500 を返す手もあるが、
        # ここではフロントぐるぐる防止を優先しACK
        return 'Generation failed (ack)', 200

    # ---------------------------
    # 6) Firestoreに書き込み（フロントの監視がこれで解除される）
    # ---------------------------
    try:
        db.collection('excuses').document(inc_id).set(result)
    except Exception as e:
        print(f"[ERROR] Firestore書き込み失敗: {e}")
        # 再試行しても二重生成の恐れ → ACKで握りつぶし
        return 'Persist failed (ack)', 200

    # ---------------------------
    # 7) GCSへの出力（入力がGCS経由だったときだけ実行）
    # 出力: output/xxx_excuses.json
    # 入力: archive/xxx.json に移動
    # ---------------------------
    try:
        if used_gcs_input:
            output_blob = bucket.blob(f"output/{inc_id}_excuses.json")
            output_blob.upload_from_string(
                json.dumps(result, indent=2, ensure_ascii=False),
                if_generation_match=0  # 既存ファイルがあれば失敗させて二重生成防止
            )
            # 元の入力をアーカイブに移動
            src_blob = bucket.blob(object_id)
            if src_blob.exists():
                bucket.copy_blob(src_blob, bucket, f"archive/{object_id}")
                src_blob.delete()
    except Exception as e:
        print(f"[WARN] GCS出力/アーカイブ処理に失敗: {e}")
        # Firestoreに書けていればフロントは進むのでACK

    # ---------------------------
    # 8) 完了ログとACK
    # ---------------------------
    print(f"[OK] {inc_id} の言い訳生成完了 (difficulty={result.get('difficulty_score')})")
    return 'OK', 200

@app.route('/health', methods=['GET'])
def health_check():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))