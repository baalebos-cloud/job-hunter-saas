FROM prom/prometheus:v2.55.1
USER root
COPY prometheus.yml.tmpl alerts.yml /etc/prometheus/
COPY --chmod=755 entrypoint.sh /etc/prometheus/entrypoint.sh
RUN chown -R nobody:nobody /etc/prometheus
USER nobody
ENTRYPOINT ["/etc/prometheus/entrypoint.sh"]
