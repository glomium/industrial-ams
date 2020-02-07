FROM envoyproxy/envoy-alpine:v1.13.0
COPY envoy.yaml /etc/envoy/envoy.yaml
CMD ["envoy", "-c", "/etc/envoy/envoy.yaml", "-l", "debug"]
