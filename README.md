# Comparison Tools

A comprehensive platform for comparing various products and services across multiple domains. This repository contains the **apartments comparison** service, hosted at [apartments.comparison.tools](https://apartments.comparison.tools).

## Platform Architecture

This is part of a larger comparison tools ecosystem:

- **apartments.comparison.tools** - Real estate and rental comparison (this app)
- *Future subdomains planned for other comparison categories*

Each subdomain operates as an independent service while sharing the unified `comparison.tools` brand.

## Features

- **User Authentication**: Complete sign-up and sign-in functionality
- **Apartment Management**: Add, edit, and delete apartment listings
- **Smart Comparison**: Compare apartments based on rent, square footage, and other criteria
- **User Preferences**: Customize weighting for price, size, and location factors
- **Responsive Design**: Mobile-friendly interface built with Tailwind CSS

## Tech Stack

- **Backend**: Django 5.2, Python 3.13.3
- **Frontend**: Tailwind CSS, Django Templates
- **Database**: SQLite (development), PostgreSQL (production)
- **Deployment**: Google App Engine
- **CI/CD**: GitHub Actions

## Local Development

### Prerequisites
- Python 3.13.3 (managed with pyenv recommended)
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/taivon/comparison-tools.git
cd comparison-tools
```

2. Ensure correct Python version (if using pyenv):
```bash
# The project includes a .python-version file, so pyenv will automatically use Python 3.13.3
pyenv install 3.13.3  # Only if not already installed
```

3. Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run database migrations:
```bash
python manage.py migrate
```

6. Start the development server:
```bash
python manage.py runserver
```

7. Visit `http://localhost:8000` in your browser

## Deployment

The application is automatically deployed to Google App Engine via GitHub Actions on every push to the main branch.

- **Production URL**: https://apartments.comparison.tools
- **Runtime**: Python 3.13 on Google App Engine

## Project Structure

```
comparison-tools/
├── apartments/          # Main Django app
├── config/             # Django settings and configuration
├── theme/              # Tailwind CSS theme
├── static/             # Static files
├── templates/          # Django templates
├── app.yaml           # Google App Engine configuration
├── requirements.txt   # Python dependencies
└── manage.py          # Django management script
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and commit: `git commit -m "Add feature"`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is private and proprietary.