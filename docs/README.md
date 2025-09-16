# GraphQL API Documentation

This directory contains the documentation for the GraphQL API library, built with Jekyll and deployed to GitHub Pages.

## Local Development

### Prerequisites

- Ruby 2.7 or newer
- Bundler gem

### Setup

1. Install dependencies:
   ```bash
   cd docs
   bundle install
   ```

2. Serve the site locally:
   ```bash
   bundle exec jekyll serve
   ```

3. Open http://localhost:4000 in your browser

### Project Structure

```
docs/
├── _config.yml          # Jekyll configuration
├── _layouts/            # Page layouts
│   └── default.html     # Main layout template
├── assets/              # CSS, JS, and other assets
│   └── css/
│       └── style.scss   # Main stylesheet
├── index.md             # Homepage
├── getting-started.md   # Getting started guide
├── examples.md          # Examples and tutorials
├── api-reference.md     # Complete API reference
├── contributing.md      # Contributing guidelines
├── Gemfile              # Ruby dependencies
└── README.md           # This file
```

## Adding Content

### New Pages

1. Create a new Markdown file in the docs directory
2. Add front matter at the top:
   ```yaml
   ---
   layout: default
   title: "Page Title"
   description: "Page description"
   ---
   ```
3. Add the page to navigation in `_config.yml` if needed

### Updating Existing Content

Simply edit the corresponding Markdown files. The site will rebuild automatically when changes are pushed to the main branch.

## Deployment

The documentation is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the main branch. The workflow is defined in `.github/workflows/pages.yml`.

## Customization

### Styling

The main stylesheet is in `assets/css/style.scss`. It imports the base theme and adds custom styling for the documentation.

### Layout

The main layout template is in `_layouts/default.html`. It includes the header, navigation, content area, and footer.

### Configuration

Site configuration is in `_config.yml`. This includes site metadata, navigation, and Jekyll settings.