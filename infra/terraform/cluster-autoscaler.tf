resource "aws_iam_role" "cluster_autoscaler" {
  name = "${var.project_name}-cluster-autoscaler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "pods.eks.amazonaws.com"
      }
      Action = [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
      Condition = {
        StringEquals = {
          "aws:RequestTag/eks-cluster-name"           = aws_eks_cluster.main.name
          "aws:RequestTag/kubernetes-namespace"       = "kube-system"
          "aws:RequestTag/kubernetes-service-account" = "cluster-autoscaler"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  name = "scale-project-node-group"
  role = aws_iam_role.cluster_autoscaler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ScaleTaggedNodeGroups"
        Effect = "Allow"
        Action = [
          "autoscaling:SetDesiredCapacity",
          "autoscaling:TerminateInstanceInAutoScalingGroup"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/k8s.io/cluster-autoscaler/enabled"                      = "true"
            "aws:ResourceTag/k8s.io/cluster-autoscaler/${aws_eks_cluster.main.name}" = "owned"
          }
        }
      },
      {
        Sid    = "ReadScalingConfiguration"
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeScalingActivities",
          "autoscaling:DescribeTags",
          "ec2:DescribeImages",
          "ec2:DescribeInstanceTypes",
          "ec2:DescribeLaunchTemplateVersions",
          "ec2:GetInstanceTypesFromInstanceRequirements",
          "eks:DescribeNodegroup"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_eks_pod_identity_association" "cluster_autoscaler" {
  cluster_name    = aws_eks_cluster.main.name
  namespace       = "kube-system"
  service_account = "cluster-autoscaler"
  role_arn        = aws_iam_role.cluster_autoscaler.arn

  depends_on = [
    aws_eks_addon.pod_identity_agent,
    aws_iam_role_policy.cluster_autoscaler
  ]
}

# 노드 그룹이 사용하는 ASG에 탐색 및 권한 제한용 태그를 직접 설정한다.
resource "aws_autoscaling_group_tag" "cluster_autoscaler" {
  for_each = {
    "k8s.io/cluster-autoscaler/enabled"                 = "true"
    "k8s.io/cluster-autoscaler/${var.project_name}-eks" = "owned"
  }

  autoscaling_group_name = aws_eks_node_group.main.resources[0].autoscaling_groups[0].name

  tag {
    key                 = each.key
    value               = each.value
    propagate_at_launch = false
  }
}
