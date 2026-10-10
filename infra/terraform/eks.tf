variable "eks_admin_cidr" {
  description = "Public IPv4 CIDR allowed to access the EKS API"
  type        = string

  validation {
    condition = (
      can(cidrnetmask(var.eks_admin_cidr)) &&
      endswith(var.eks_admin_cidr, "/32")
    )
    error_message = "Enter a single public IPv4 address with /32."
  }
}

# EKS 클러스터가 사용하는 IAM 역할
resource "aws_iam_role" "eks_cluster" {
  name = "${var.project_name}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# EKS 클러스터
resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-eks"
  version  = "1.35"
  role_arn = aws_iam_role.eks_cluster.arn

  bootstrap_self_managed_addons = true

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  upgrade_policy {
    support_type = "STANDARD"
  }

  vpc_config {
    subnet_ids = aws_subnet.private[*].id

    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = [var.eks_admin_cidr]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster
  ]
}

# 워커 노드가 사용하는 IAM 역할
resource "aws_iam_role" "eks_node" {
  name = "${var.project_name}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_node_worker" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_node_ecr" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly"
}

# 이번 실습에서는 CNI 권한을 노드 역할에 부여
resource "aws_iam_role_policy_attachment" "eks_node_cni" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

# 관리형 워커 노드: 초기 1대, 자동 확장 최대 2대
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-nodes"
  node_role_arn   = aws_iam_role.eks_node.arn

  subnet_ids = aws_subnet.public[*].id
  version    = aws_eks_cluster.main.version

  capacity_type  = "ON_DEMAND"
  instance_types = ["t3.large"]
  ami_type       = "AL2023_x86_64_STANDARD"
  disk_size      = 20

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 2
  }

  # 실행 중 desired_size는 Cluster Autoscaler가 관리한다.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    workload = "movie-review"
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_node_worker,
    aws_iam_role_policy_attachment.eks_node_ecr,
    aws_iam_role_policy_attachment.eks_node_cni,
    aws_route_table_association.public
  ]
}

output "eks_cluster_name" {
  value = aws_eks_cluster.main.name
}

output "eks_node_group_name" {
  value = aws_eks_node_group.main.node_group_name
}
