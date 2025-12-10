# Performance Monitoring & Tracing

This document explains how to monitor and trace performance in Google App Engine.

## Built-in Monitoring

### 1. App Engine Request Logs
App Engine automatically logs all requests with timing information. View them in:
- **Google Cloud Console** → **App Engine** → **Logs**
- Filter by: `resource.type="gae_app"`

Each log entry includes:
- Request duration
- Status code
- Request path
- Response size

### 2. Request Timing Middleware
We've added custom middleware (`config.trace_middleware.RequestTimingMiddleware`) that logs detailed timing for each request:

- **Duration**: Total request time
- **CPU Time**: Actual CPU processing time
- **Method & Path**: HTTP method and URL path
- **Status Code**: Response status

View these logs in Cloud Logging with:
```
resource.type="gae_app"
jsonPayload.method="GET"  # or POST, etc.
jsonPayload.duration_seconds>1.0  # Find slow requests
```

### 3. Google Cloud Profiler (Optional)
Cloud Profiler provides CPU and memory profiling. 

**Note:** Currently disabled due to Python 3.13 compatibility issues with `google-cloud-profiler`. The package doesn't support Python 3.13 yet. You can still use the request timing middleware for performance monitoring.

**To enable in the future** (when Python 3.13 support is added):
1. Install `google-cloud-profiler` package
2. Enable Profiler API:
   ```bash
   gcloud services enable cloudprofiler.googleapis.com --project=comparison-tools-479102
   ```
3. Grant Profiler Agent Role:
   ```bash
   SERVICE_ACCOUNT="comparison-tools-479102@appspot.gserviceaccount.com"
   gcloud projects add-iam-policy-binding comparison-tools-479102 \
       --member="serviceAccount:${SERVICE_ACCOUNT}" \
       --role="roles/cloudprofiler.agent"
   ```

## Finding Slow Requests

### In Cloud Logging:
1. Go to **Cloud Logging** → **Logs Explorer**
2. Use this query to find slow requests:
```
resource.type="gae_app"
jsonPayload.duration_seconds>1.0
```
3. Sort by `duration_seconds` to find the slowest requests

### Using Trace IDs:
App Engine automatically adds trace IDs to requests. Use them to:
1. Find a request in logs
2. Copy the trace ID
3. Search for all logs with that trace ID to see the full request flow

## Viewing Traces in Google Cloud Trace

### Enable Cloud Trace API:
```bash
gcloud services enable cloudtrace.googleapis.com --project=comparison-tools-479102
```

### View Traces in Cloud Console:

**Method 1: From Logs Explorer**
1. Go to **Cloud Logging** → **Logs Explorer**
2. Find a log entry for a request
3. Look for the `trace` field in the log entry
4. Click on the trace ID (it will be a long hex string)
5. This opens the trace in **Cloud Trace**

**Method 2: Direct Access to Cloud Trace**
1. Go to **Google Cloud Console** → **Trace** (or search for "Trace")
2. Select your project: `comparison-tools-479102`
3. You'll see a timeline of all traces
4. Filter by:
   - Service: `gae_app` or `default`
   - Time range
   - Latency threshold (e.g., show only slow requests)

**Method 3: Using Trace ID from Logs**
1. In **Cloud Logging**, find a request log
2. Copy the trace ID from the log entry (look for `trace` field)
3. Go to **Cloud Trace**
4. Paste the trace ID in the search box
5. View the detailed trace timeline

### Understanding Trace Data:

Each trace shows:
- **Spans**: Individual operations within a request
- **Timeline**: Visual representation of when each operation occurred
- **Duration**: How long each operation took
- **Nested spans**: Operations that happen within other operations

### Finding Slow Traces:

In **Cloud Trace**:
1. Use the latency filter (e.g., "Show traces slower than 1s")
2. Sort by duration
3. Click on a trace to see the detailed breakdown
4. Look for long spans to identify bottlenecks

### Trace Query Examples:

In **Cloud Logging**, you can query by trace:
```
resource.type="gae_app"
trace="projects/comparison-tools-479102/traces/TRACE_ID_HERE"
```

Replace `TRACE_ID_HERE` with an actual trace ID from a log entry.

## Performance Tips

1. **Database Queries**: Check for N+1 queries in Django logs
2. **External APIs**: Look for slow external API calls (Google Maps, Stripe, etc.)
3. **Static Files**: Ensure static files are served efficiently (they are via App Engine handlers)
4. **Caching**: Check cache hit rates in logs

## Monitoring Dashboard

Create a custom dashboard in **Cloud Monitoring**:
1. Go to **Monitoring** → **Dashboards**
2. Create new dashboard
3. Add charts for:
   - Request latency (p50, p95, p99)
   - Request rate
   - Error rate
   - CPU utilization

## Alerts

Set up alerts for:
- High latency (p95 > 2 seconds)
- High error rate (> 1%)
- High CPU utilization (> 80%)

Go to **Monitoring** → **Alerting** → **Create Policy**

