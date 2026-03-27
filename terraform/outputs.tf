output "postgres_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "The connection endpoint for the PostgreSQL database."
}

output "loadbalancer_url" {
  value       = aws_lb.main.dns_name
  description = "The public DNS name of the Load Balancer. Access your app here."
}

output "redis_endpoint" {
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
  description = "The endpoint for the Redis ElastiCache cluster."
}
