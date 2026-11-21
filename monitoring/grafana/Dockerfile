FROM grafana/grafana:11.3.1
COPY provisioning /etc/grafana/provisioning
COPY dashboards /etc/grafana/dashboards
ENV GF_AUTH_ANONYMOUS_ENABLED=false \
    GF_USERS_ALLOW_SIGN_UP=false \
    GF_ANALYTICS_REPORTING_ENABLED=false \
    GF_SERVER_HTTP_PORT=3000
