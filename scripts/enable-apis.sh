#!/bin/bash

# Script to enable required Google Cloud APIs for App Engine deployment
# Run this once to enable all necessary APIs

PROJECT_ID="comparison-tools-479102"

echo "Enabling required APIs for App Engine deployment..."

gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable appengine.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudresourcemanager.googleapis.com --project=$PROJECT_ID
gcloud services enable storage-component.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudprofiler.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudtrace.googleapis.com --project=$PROJECT_ID

echo ""
echo "✅ APIs enabled successfully!"
echo ""
echo "Setting up Cloud Profiler permissions..."
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudprofiler.agent" \
    --condition=None 2>/dev/null || echo "Note: Profiler permissions may already be set"
echo ""
echo "Wait a few minutes for the APIs to propagate, then try deploying again."

