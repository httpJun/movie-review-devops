# EKS 모니터링 실습

## 구성

- 검증일: 2026-10-04
- Helm chart: prometheus-community/kube-prometheus-stack 91.9.0
- Helm release / namespace: monitoring
- 환경: EKS 1.35, t3.large 워커 노드 1대, 루트 디스크 20GiB
- 구성 요소: Prometheus, Grafana, Prometheus Operator,
  kube-state-metrics, node-exporter
- 접속: ClusterIP Service와 로컬 포트포워딩
- Prometheus 보관 설정: 6시간 / 512MB
- Prometheus 임시 저장소: emptyDir, sizeLimit 2Gi
- Grafana 영속 저장소 및 Alertmanager 비활성화

보관 크기는 WAL 등을 포함한 전체 디스크 사용량의 엄격한 상한이 아니다.
Pod 또는 클러스터 삭제 시 임시 저장된 지표와 Grafana 변경 사항이 사라질 수 있다.

## 설치

저장소 루트에서 실행한다.
EKS 연결과 movie-app 배포 및 DB 마이그레이션이 완료된 상태를 전제로 한다.

```bash
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring \
  prometheus-community/kube-prometheus-stack \
  --version "$(cat k8s/monitoring/chart-version.txt)" \
  --kube-context movie-review-eks \
  --namespace monitoring \
  --create-namespace \
  --values k8s/monitoring/values-demo.yaml \
  --wait --timeout 10m
```

## Grafana 접속

```bash
kubectl --context movie-review-eks -n monitoring \
  port-forward svc/monitoring-grafana 3001:80
```

- URL: http://localhost:3001
- 사용자: admin
- 초기 비밀번호는 아래 명령으로 로컬에서 확인한다.
- 비밀번호와 Secret이 포함된 출력은 Git이나 캡처에 저장하지 않는다.
- UI에서 비밀번호를 변경했다면 변경한 비밀번호를 사용한다.

```bash
kubectl --context movie-review-eks -n monitoring \
  get secret monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 --decode
printf '\n'
```

## 검증 결과

- 모니터링 구성 요소의 모든 Pod가 Ready 상태인 것을 확인했다.
- 모든 Service는 ClusterIP이고 PVC는 생성되지 않았다.
- movie-app의 backend, frontend, postgres Pod에 대한 Ready 지표를 확인했다.
- Completed 상태의 마이그레이션 Pod는 Ready=0으로 표시됨을 확인했다.
- Pod별 CPU, 메모리, 네트워크 지표가 Grafana에 표시되는 것을 확인했다.
- 노드 CPU, 메모리, 디스크 지표가 표시되는 것을 확인했다.
- 기본 상태 캡처 시 노드 메모리 사용률은 약 30.5%,
  루트 디스크 사용률은 약 49.3%, 가용 공간은 약 10.8GB였다.
- backend 컨테이너에서 120초간 인위적인 CPU 부하를 발생시켰다.
- 실행 시각: 2026-10-04 15:56:13~15:58:13 KST.
- 대시보드에서 backend CPU가 약 0.4코어까지 상승한 후
  부하 종료 이후 평상 수준으로 하락하는 흐름을 확인하고 캡처했다.
- 부하 후 앱 Pod는 모두 Ready이고 재시작 횟수는 0이었다.
- 노드 DiskPressure=False를 확인했다.

그래프의 값은 쿼리 집계 구간에 영향을 받으며 순간 최대 CPU 사용량과 다를 수 있다.
검증 화면의 시간대는 UTC였으며 KST보다 9시간 느리게 표시됐다.

## 확인한 대시보드

- Kubernetes / Compute Resources / Namespace (Pods)
  - namespace: movie-app
  - CPU 및 메모리 사용량, requests/limits 비교, 네트워크
- Node Exporter / Nodes
  - CPU, 메모리, 디스크 공간 및 I/O, 네트워크

## 사용한 PromQL

Pod별 Ready 상태:

```promql
max by (pod) (
  kube_pod_status_ready{namespace="movie-app",condition="true"}
)
```

수집 대상 상태 조회:

```promql
up
```

up=1은 해당 대상의 수집 성공, up=0은 수집 실패를 뜻한다.
Pod Ready 지표와는 다른 의미다.

## CPU 부하 재현

아래 명령은 backend 컨테이너 안에서 계산을 수행하고 120초 후 종료한다.
실습 환경에서 한 번 실행하고 Grafana에서 상승·하락을 확인한다.

```bash
kubectl --context movie-review-eks -n movie-app \
  exec deployment/backend -c backend -- \
  python -u -c '
import time
from datetime import datetime, timezone

print("CPU load start:", datetime.now(timezone.utc).isoformat(), flush=True)
deadline = time.monotonic() + 120
while time.monotonic() < deadline:
    sum(i * i for i in range(10000))
print("CPU load end:", datetime.now(timezone.utc).isoformat(), flush=True)
'
```

## 검증 범위와 제한

- 인위적인 CPU 부하를 지표와 그래프로 관찰한 실습이다.
- 실제 사용자 트래픽의 처리량, 응답 시간, 서비스 성능을 측정한 것은 아니다.
- 이번 클러스터에는 HPA와 Argo CD를 설치하지 않았다.
  기존 GitOps Deployment 파일을 kubectl로 직접 적용했다.
- HPA 확장·축소와 Argo CD 자동 배포는 이전 실습에서 별도로 검증했다.
- 애플리케이션의 HTTP 요청 수·지연 시간 등 전용 지표는 추가하지 않았다.
- 외부 알림 전송, 장기 보관, 모니터링 고가용성은 검증하지 않았다.
- 캡처에는 비밀번호와 Secret을 포함하지 않는다.

## 종료 및 비용 관리

Grafana 포트포워딩을 종료해도 AWS 리소스는 삭제되지 않는다.
실습 종료 시 Terraform 삭제 계획을 확인하고 EKS와 노드를 정리한다.
이후 EKS, EC2, EBS, 로드밸런서, NAT Gateway, Elastic IP 잔존 여부를 확인한다.
보존한 ECR 이미지에는 저장 비용이 남을 수 있다.
