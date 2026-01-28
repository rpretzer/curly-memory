"""Seed companies from companies.yaml into the database."""

import sys
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db import get_db_context
from app.models import Company, normalize_text


def seed_companies():
    """Seed companies from companies.yaml."""

    # Load companies from YAML
    yaml_path = Path(__file__).parent.parent / "data" / "companies.yaml"
    print(f"Loading companies from: {yaml_path}")

    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: {yaml_path} not found")
        return False
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")
        return False

    companies_data = data.get('companies', [])
    print(f"Found {len(companies_data)} companies in YAML")

    with get_db_context() as db:
        added = 0
        updated = 0
        errors = []

        for company_data in companies_data:
            try:
                name = company_data['name']
                normalized = normalize_text(name)

                # Check if company already exists
                existing = db.query(Company).filter(Company.normalized_name == normalized).first()

                if existing:
                    # Update existing company
                    existing.name = company_data['name']
                    existing.industries = company_data.get('industries')
                    existing.verticals = company_data.get('verticals')
                    existing.size = company_data.get('size')
                    existing.stage = company_data.get('stage')
                    existing.tech_stack = company_data.get('tech_stack')
                    existing.description = company_data.get('description', '').strip()
                    existing.headquarters = company_data.get('headquarters')
                    existing.greenhouse_token = company_data.get('greenhouse_token')
                    existing.workday_slug = company_data.get('workday_slug')
                    existing.website = company_data.get('website')
                    updated += 1
                    print(f"  ✓ Updated: {name}")
                else:
                    # Create new company
                    company = Company(
                        name=company_data['name'],
                        normalized_name=normalized,
                        industries=company_data.get('industries'),
                        verticals=company_data.get('verticals'),
                        size=company_data.get('size'),
                        stage=company_data.get('stage'),
                        tech_stack=company_data.get('tech_stack'),
                        description=company_data.get('description', '').strip(),
                        headquarters=company_data.get('headquarters'),
                        greenhouse_token=company_data.get('greenhouse_token'),
                        workday_slug=company_data.get('workday_slug'),
                        website=company_data.get('website')
                    )
                    db.add(company)
                    added += 1
                    print(f"  ✓ Added: {name}")

            except KeyError as e:
                error_msg = f"Missing required field {e} for company: {company_data.get('name', 'unknown')}"
                errors.append(error_msg)
                print(f"  ✗ Error: {error_msg}")
            except Exception as e:
                error_msg = f"Error processing {company_data.get('name', 'unknown')}: {e}"
                errors.append(error_msg)
                print(f"  ✗ Error: {error_msg}")

        try:
            db.commit()
            print(f"\n✓ Seeding completed successfully")
            print(f"  - Added: {added} companies")
            print(f"  - Updated: {updated} companies")
            if errors:
                print(f"  - Errors: {len(errors)}")
                for error in errors:
                    print(f"    {error}")
            return True
        except Exception as e:
            db.rollback()
            print(f"\n✗ Failed to commit changes: {e}")
            return False


if __name__ == "__main__":
    print("Seeding companies into database...\n")
    success = seed_companies()
    sys.exit(0 if success else 1)
