# EKS 노드 자동 확장·축소 검증

## 목적과 범위

2026-10-10 CPU requests 부족으로 스케줄링되지 않는 Pod가 발생했을 때
Cluster Autoscaler가 EC2 노드를 추가하고, 테스트 Pod 제거 후 노드를
자동 축소하는 과정을 검증했습니다.

기존 HPA 검증과는 별도 실험입니다. HPA에서 시작해 노드 확장까지 이어지는
통합 부하 시험이나 실제 사용자 트래픽 성능 시험은 수행하지 않았습니다.

## 구성

| 항목 | 설정 |
|---|---|
| 리전·클러스터 | ap-northeast-2 / movie-review-eks |
| Kubernetes | EKS 1.35, 관측한 노드 버전 1.35.8 |
| Autoscaler | 1.35.0 / Helm chart 9.59.0 |
| 노드 그룹 | movie-review-nodes |
| 노드 | ON_DEMAND t3.large, 퍼블릭 서브넷 |
| 확장 범위 | 초기 1대, 최소 1대, 최대 2대 |
| AWS 인증 | EKS Pod Identity / kube-system의 cluster-autoscaler ServiceAccount |
| 확장 후 축소 대기 | scale-down-delay-after-add: 10m |
| 불필요 노드 유지 시간 | scale-down-unneeded-time: 10m |

Terraform은 노드 그룹의 desired_size 변경을 무시하도록 설정했습니다.
실행 중 목표 노드 수는 Cluster Autoscaler가 관리합니다.
노드 변경 IAM 권한은 Autoscaler 태그 조건으로 대상 ASG를 제한했습니다.

## 검증 절차

1. 노드 1대 Ready와 Autoscaler 실행 상태를 확인했습니다.
2. 각각 CPU 1코어를 요청하는 테스트 Pod 2개를 배포했습니다.
3. 한 Pod의 Insufficient cpu 및 Pending 상태를 확인했습니다.
4. TriggeredScaleUp 이벤트와 ASG의 1 → 2 변경을 확인했습니다.
5. 새 노드 Ready와 각 노드에 배치된 테스트 Pod의 Running을 확인했습니다.
6. 테스트 Deployment의 replicas를 0으로 줄였습니다.
7. Autoscaler의 축소 로그, ASG 인스턴스 종료 성공, 노드 1대 Ready를 확인했습니다.

테스트 컨테이너는 대기 명령을 실행했습니다. CPU를 실제로 소모하는 대신
CPU requests로 스케줄링 용량 부족을 재현했습니다.
노드 축소 검증 중 ASG desired capacity를 수동 변경하거나 노드를 수동 삭제하지 않았습니다.

## 관측 결과

모든 시각은 UTC입니다. 한국 시각은 9시간을 더합니다.

| 시각 | 관측 |
|---|---|
| 06:35:19 | 확장 테스트 시작 기록 |
| 06:35:30 | ASG 활동 Cause에 목표 용량 1 → 2 변경 기록 |
| 06:35:42.553 | 추가 EC2 시작 활동의 StartTime, 최종 상태 Successful |
| 06:36:40.442 | Autoscaler가 확장 성공을 기록, 로그상 소요 약 1분 10초 |
| 06:41:11 | 테스트 Pod를 0개로 줄이는 축소 테스트 시작 기록 |
| 06:51:59.119 | 추가 EC2 종료 활동의 StartTime, 최종 상태 Successful |
| 최종 조회 | ASG Desired=1, InService 1대, Kubernetes 노드 1대 Ready |

축소 테스트 시작부터 EC2 종료 활동 시작까지 약 10분 48초가 걸렸습니다.
이는 EC2 종료 완료까지의 시간이나 서비스 중단 시간이 아닙니다.
확장 소요 약 1분 10초도 Autoscaler 내부 관측값이며,
테스트 시작부터 Pod Ready까지의 시간과 구분합니다.

노드 초기화 중 일시적인 FailedCreatePodSandBox 이벤트가 관측됐지만,
이후 해당 Pod가 Running 상태에 도달했습니다.

## 증거

- [확장 전 노드](evidence/cluster-autoscaler/nodes-before.txt)
- [확장 후 노드](evidence/cluster-autoscaler/nodes-scaled-up.txt)
- [확장 후 Pod 배치](evidence/cluster-autoscaler/pods-scaled-up.txt)
- [확장 이벤트](evidence/cluster-autoscaler/events-scale-up.txt)
- [확장 로그](evidence/cluster-autoscaler/autoscaler-scale-up.log)
- [축소 이벤트](evidence/cluster-autoscaler/events-scale-down.txt)
- [축소 로그](evidence/cluster-autoscaler/autoscaler-scale-down.log)
- [최종 Autoscaler 로그](evidence/cluster-autoscaler/autoscaler-final.log)
- [ASG 최종 상태](evidence/cluster-autoscaler/asg-after-scale-down.json)
- [EC2 시작·종료 활동](evidence/cluster-autoscaler/scaling-activities.json)
- [축소 후 노드](evidence/cluster-autoscaler/nodes-after-scale-down.txt)
- [확장 시작 시각](evidence/cluster-autoscaler/scale-up-start.txt)
- [축소 시작 시각](evidence/cluster-autoscaler/scale-down-start.txt)

## 구현 파일

- [IAM·Pod Identity·ASG 태그](../infra/terraform/cluster-autoscaler.tf)
- [EKS 노드 그룹과 lifecycle](../infra/terraform/eks.tf)
- [Helm 설정](../k8s/cluster-autoscaler/values.yaml)
- [차트 버전](../k8s/cluster-autoscaler/chart-version.txt)
- [테스트 Deployment](../k8s/cluster-autoscaler/scale-test.yaml)

## 종료와 한계

검증 후 Terraform 삭제 계획을 검토하고 실습 리소스 8개를 삭제했습니다.
AWS CLI에서 EKS 클러스터 목록이 비어 있고, 실습 EC2 2대가 terminated이며,
서울 리전 EBS 볼륨 목록이 비어 있음을 확인했습니다.
보존한 ECR 이미지에는 저장 비용이 남을 수 있습니다.

이번 검증은 단기 실습입니다. EKS 앱의 다중 AZ 고가용성, 무중단 배포,
노드 장애 복구, 프라이빗 워커 구성 및 장기 운영 안정성은 검증하지 않았습니다.
