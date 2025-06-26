# Docker Deployment with GitHub Actions

This repository includes a GitHub Actions workflow that automatically builds and publishes a Docker image to GitHub Container Registry (ghcr.io).

## How it Works

The workflow (`.github/workflows/docker-build-push.yml`) automatically:

1. **Triggers** on every push to the `main` branch
2. **Builds** the Docker image using the provided Dockerfile
3. **Pushes** the image to `ghcr.io/[your-username]/finger-web:latest`

## Setup Requirements

### 1. Repository Settings
Ensure your repository has the following settings configured:

- **Actions**: GitHub Actions must be enabled for your repository
- **Packages**: Container registry permissions must be enabled

### 2. Branch Configuration
The workflow is configured to trigger on pushes to the `main` branch. If your default branch has a different name (e.g., `master`), update the workflow file:

```yaml
on:
  push:
    branches: [ your-branch-name ]  # Change 'main' to your branch name
```

### 3. Permissions
The workflow uses the built-in `GITHUB_TOKEN` which automatically has the necessary permissions. No additional secrets need to be configured.

## Using the Docker Image

### Pull and Run
Once the workflow runs successfully, you can pull and run your image:

```bash
# Pull the latest image
docker pull ghcr.io/[your-username]/finger-web:latest

# Run the container
docker run -p 5000:5000 ghcr.io/[your-username]/finger-web:latest
```

### Docker Compose
You can also update your `docker-compose.yml` to use the published image:

```yaml
version: '3.8'
services:
  finger-web:
    image: ghcr.io/[your-username]/finger-web:latest
    ports:
      - "5000:5000"
```

## Manual Trigger

The workflow can also be triggered manually:

1. Go to your repository on GitHub
2. Click on the "Actions" tab
3. Select "Build and Push Docker Image" workflow
4. Click "Run workflow"

## Workflow Features

- **Automatic tagging**: Images are tagged with `latest` for main branch pushes
- **Build caching**: Uses GitHub Actions cache to speed up builds
- **Security**: Uses GitHub's built-in authentication tokens
- **Metadata**: Includes proper OCI labels and build information

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure GitHub Actions and Container Registry are enabled in repository settings
2. **Branch Mismatch**: Verify the workflow triggers on your default branch name
3. **Build Failures**: Check the Actions tab for detailed build logs

### Viewing Build Status

Monitor your builds in the GitHub Actions tab of your repository. Each push to main will show a new workflow run with detailed logs.
