# FireMon Report Schedule Extractor

A Python tool to extract report schedules from FireMon Security Manager API and generate comprehensive Excel reports with multiple views, conflict detection, and schedule analysis.

## Features

- **Automated Data Extraction**: Fetches report schedules and device groups from FireMon API
- **Multiple Excel Views**: 
  - Detailed schedule listings
  - Matrix views by tower/department
  - Time slot analysis
- **Smart Categorization**: Automatically categorizes reports by type
- **Conflict Detection**: Highlights duplicate schedules and missing reports
- **Timezone Support**: Configurable timezone conversion
- **Cache Support**: Falls back to cached data if API is unavailable
- **Customizable Organization**: Easy to customize for your organization's naming conventions

## Requirements

- Python 3.7+
- FireMon Security Manager API access
- Required Python packages (see requirements.txt)

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd FireMon-Report-Pull
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your FireMon credentials:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
FIREMON_BASE_URL=https://your-firemon-server.com/securitymanager/api/domain/1
FIREMON_USER=your_username
FIREMON_PASS=your_password
FIREMON_VERIFY_SSL=false
```

### Customization

The script includes two main customization points for your organization:

#### 1. Tower/Department Classification (`infer_tower` function)

Customize how device groups are classified into towers/departments. Edit the `infer_tower()` function around line 200:

```python
def infer_tower(device_group_name: str, report_name: str) -> str:
    # Add your organization's classification rules
    if 'datacenter' in report_name.lower():
        return 'DATA_CENTER'
    # ... more rules
```

Example towers: `DATA_CENTER`, `CORPORATE`, `WAN`, `CLOUD`, `BRANCH`

#### 2. Report Categories (`extract_category` function)

Customize report categorization. Edit the `extract_category()` function around line 430:

```python
def extract_category(report_name: str, tower: str = '') -> str:
    # Add your organization's report categories
    if 'wide open' in report_name.lower():
        return 'Wide-open rules'
    # ... more categories
```

## Usage

### Basic Usage

```bash
python firemon_report_extractor.py
```

This will:
1. Fetch reports and device groups from FireMon API
2. Generate an Excel file: `firemon-report_schedules_YYYYMMDD_HHMMSS.xlsx`
3. Save JSON cache files for offline use

### Advanced Usage

```bash
# Custom output prefix
python firemon_report_extractor.py --prefix my-reports

# Custom timezone offset (e.g., PST is -8 hours from UTC)
python firemon_report_extractor.py --timezone-offset -8

# Combine options
python firemon_report_extractor.py --prefix quarterly --timezone-offset -5
```

### Command-Line Options

- `--prefix`: Output file prefix (default: `firemon-report`)
- `--timezone-offset`: Timezone offset from UTC in hours (default: `-5` for EST)

## Output

The script generates an Excel file with multiple sheets:

1. **All Schedules**: Complete list of all report schedules with details
2. **All Schedules Matrix**: Matrix view showing all device groups vs report categories
3. **[Tower] Sheets**: Individual sheets for each tower/department
4. **[Tower] Matrix**: Matrix views for each individual tower
5. **Time Slot Analysis**: Shows which device groups run at each time slot

### Excel Highlighting

- **Yellow/Orange/Pink cells**: Duplicate schedules (same time for multiple reports)
- **Red cells**: Missing reports (device group has some reports but is missing this category)
- **Empty cells**: No reports configured for this combination

## Cache Files

The script saves two JSON files for caching:

- `{prefix}.json`: Raw report data from FireMon API
- `{prefix}-devicegroups.json`: Device group data from FireMon API

These files allow the script to work offline or when the API is unavailable.

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL certificate errors, set `FIREMON_VERIFY_SSL=false` in your `.env` file.

### Authentication Errors

Verify your credentials in the `.env` file and ensure your FireMon user has API access permissions.

### No Data Returned

- Check your FireMon base URL is correct
- Verify domain ID in the URL (usually `/domain/1`)
- Ensure your user has permissions to view reports and device groups

### Import Errors

Make sure all required packages are installed:
```bash
pip install -r requirements.txt
```

## Development

### Project Structure

```
FireMon-Report-Pull/
├── firemon_report_extractor.py   # Main script
├── requirements.txt               # Python dependencies
├── .env.example                   # Example environment file
├── .gitignore                     # Git ignore patterns
└── README.md                      # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Security Notes

- Never commit your `.env` file with actual credentials
- Use environment variables or secure credential storage
- Consider using a service account with minimal required permissions
- Regularly rotate API credentials

## License

This project is provided as-is for use with FireMon Security Manager.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review FireMon API documentation
3. Open an issue in this repository

## Changelog

### Version 1.0.0
- Initial release
- Basic report schedule extraction
- Excel output with multiple views
- Conflict detection and highlighting
- Timezone support
- Cache functionality
