#!/bin/bash
MODEL="openai_gpt-oss-20b-MXFP4.gguf"
URL="http://localhost:8000/v1/completions"

run_test() {
  PROMPT="$1"
  echo "--- PROMPT: $PROMPT ---"
  START=$(date +%s.%N)
  RESP=$(curl -s $URL \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"$MODEL\",
      \"prompt\": \"$PROMPT\",
      \"temperature\": 0.1,
      \"max_tokens\": 64,
      \"stop\": [\"Note:\", \"解説\", \"ありがとうございます\", \"Sure\", \"So \"]
    }" | jq -r '.choices[0].text')
  END=$(date +%s.%N)
  TIME=$(echo "$END - $START" | bc)
  echo "Answer: $RESP"
  echo "Time: ${TIME}s"
  echo
}

# テストケース群
run_test "次の計算の答えのみを半角数字で出力。桁区切り・説明禁止。 12345 × 6789"
run_test "次の式を既約分数で答えのみ出力。帯分数や小数は禁止。 (5/6) + (7/8)"
run_test "√2 を小数点以下10桁まで答えのみ出力。説明禁止。"
run_test "太郎は次郎より年上、次郎は三郎より年下。この3人を年齢順に並べよ。答えのみを「太郎>次郎>三郎」の形式で出力。説明禁止。"
run_test "数列: 2, 4, 8, 16, ? 答えのみを数字で出力。"
run_test "富士山の標高をメートルで答えのみ出力。"
run_test "水の沸点は摂氏何度か。答えのみ出力。"
run_test "「私は本を読んでいます」を自然な英語に翻訳。答えのみ出力。説明禁止。"
run_test "Translate into Japanese: \"The weather is nice today.\" 答えのみを自然な日本語1文で出力。説明禁止。"
run_test "(3 + 4i) ÷ (1 - 2i) を a + bi 形式で出力。説明禁止。"
run_test "(x + 2)(x - 3) を展開し、答えのみ出力。説明禁止。"
