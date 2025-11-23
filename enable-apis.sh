#!/bin/bash

# Script to enable required Google Cloud APIs for App Engine deployment
# Run this once to enable all necessary APIs

PROJECT_ID="comparison-tools-479102"

echo "Enabling required APIs for App Engine deployment..."

gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable appengine.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudresourcemanager.googleapis.com --project=$PROJECT_ID
gcloud services enable storage-component.googleapis.com --project=$PROJECT_ID

echo ""
echo "✅ APIs enabled successfully!"
echo ""
echo "Wait a few minutes for the APIs to propagate, then try deploying again."

