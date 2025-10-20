# M1 Observability Bootstrap

## 1. Langfuse 기본 설정
- 환경 변수
  ```
  LANGFUSE_PUBLIC_KEY=<team-public-key>
  LANGFUSE_SECRET_KEY=<team-secret-key>
  LANGFUSE_HOST=https://cloud.langfuse.com
  ```
- LiteLLM 측 설정 (`litellm_config.yaml`)
  ```yaml
  general_settings:
    callbacks: [langfuse]
  ```
- 파이프라인에 트레이스 식별자 추가 예시  
  ```python
  import langfuse
  tracer = langfuse.Client()
  with tracer.trace(name="m1_process_filing") as span:
      # classify → extract → self-check → summarize
  ```

## 2. Promptfoo Smoke
- `eval/promptfoo/m1_classification.yaml` (예시)
  ```yaml
  prompts:
    - file: ../../llm/prompts/classify_filing.py
  providers:
    - id: openai:gpt-4o-mini
  ```
- 실행: `npx promptfoo@latest eval eval/promptfoo/m1_classification.yaml`

## 3. Ragas Skeleton
- `eval/ragas/m1_self_check.py` (TODO):  
  - Qdrant에서 context 추출  
  - 요약/정답 → Ragas faithfulness, answer relevance 계산

## 4. 알림 & 대시보드 연동
- Celery 실패 태스크: Sentry 혹은 Slack webhook 연결
- Grafana 메트릭 (향후):  
  - 처리 시간 히스토그램 (ingest→completed)  
  - Self-check 실패율  
  - Qdrant 인덱싱 지연

> 위 스텁은 필수 설정과 최소 툴링 위치만 정의한 것으로, 실제 키 발급 및 대시보드 구성은 운영 환경에서 진행한다.
