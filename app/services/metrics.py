from dataclasses import dataclass


@dataclass
class MetricsStore:
    payments_created_total: int = 0
    payments_fetched_total: int = 0
    payment_processing_success_total: int = 0
    payment_processing_failed_total: int = 0
    webhook_failures_total: int = 0
    dlq_published_total: int = 0
    dlq_consumed_total: int = 0
    dlq_invalid_payload_total: int = 0
    dlq_status_update_failed_total: int = 0
    dlq_webhook_delivery_failed_total: int = 0

    def to_prometheus(self) -> str:
        lines = [
            "# HELP payments_created_total Number of created payments",
            "# TYPE payments_created_total counter",
            f"payments_created_total {self.payments_created_total}",
            "# HELP payments_fetched_total Number of fetched payments",
            "# TYPE payments_fetched_total counter",
            f"payments_fetched_total {self.payments_fetched_total}",
            "# HELP payment_processing_success_total Successfully processed payments",
            "# TYPE payment_processing_success_total counter",
            f"payment_processing_success_total {self.payment_processing_success_total}",
            "# HELP payment_processing_failed_total Failed processed payments",
            "# TYPE payment_processing_failed_total counter",
            f"payment_processing_failed_total {self.payment_processing_failed_total}",
            "# HELP webhook_failures_total Webhook delivery failures",
            "# TYPE webhook_failures_total counter",
            f"webhook_failures_total {self.webhook_failures_total}",
            "# HELP dlq_published_total Messages sent to dead letter queue",
            "# TYPE dlq_published_total counter",
            f"dlq_published_total {self.dlq_published_total}",
            "# HELP dlq_consumed_total Messages consumed from dead letter queue",
            "# TYPE dlq_consumed_total counter",
            f"dlq_consumed_total {self.dlq_consumed_total}",
            "# HELP dlq_invalid_payload_total DLQ messages due to invalid payload",
            "# TYPE dlq_invalid_payload_total counter",
            f"dlq_invalid_payload_total {self.dlq_invalid_payload_total}",
            "# HELP dlq_status_update_failed_total DLQ messages due to status update failure",
            "# TYPE dlq_status_update_failed_total counter",
            f"dlq_status_update_failed_total {self.dlq_status_update_failed_total}",
            "# HELP dlq_webhook_delivery_failed_total DLQ messages due to webhook failure",
            "# TYPE dlq_webhook_delivery_failed_total counter",
            f"dlq_webhook_delivery_failed_total {self.dlq_webhook_delivery_failed_total}",
        ]
        return "\n".join(lines) + "\n"


metrics_store = MetricsStore()
