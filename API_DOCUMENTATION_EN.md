# PDF Form Service API Documentation

## Overview

The PDF Form Service provides comprehensive PDF form processing capabilities, including field parsing, form filling, and other operations.

**Base URL**: `http://{ip}:8000`

## Common Response Format

All API responses follow the following format:

### Success Response
```json
{
  "success": true,
  "message": "Operation success message",
  "data": {...}  // Specific data
}
```

### Error Response
```json
{
  "detail": "Error description"
}
```

## API Endpoints

### 1. Health Check

**Endpoint**: `GET /health`

**Description**: Check service running status

**Request Parameters**: None

**Response Example**:
```json
{
  "status": "healthy",
  "service": "pdf-form-service"
}
```

---

### 2. Get Service Information

**Endpoint**: `GET /`

**Description**: Get service basic information and available endpoints

**Request Parameters**: None

**Response Example**:
```json
{
  "message": "PDF Form Processing Service",
  "version": "1.0.0",
  "endpoints": {
    "parse_form": "/api/v1/parse-form",
    "fill_form": "/api/v1/fill-form"
  }
}
```

---

### 3. Parse PDF Form Fields

**Endpoint**: `POST /api/v1/parse-form`

**Description**: Parse all field information from a PDF form

**Request Format**: `multipart/form-data`

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | File | Yes | PDF file |

**Request Example**:
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form' \
--header 'Content-Type: application/json' \
--form 'file=@"/path/to/form.pdf"'
```

**Response Format**:
```json
{
  "success": true,
  "message": "PDF form parsing successful",
  "fields": [
    {
      "name": "field_name",
      "label": "field_label",
      "type": "field_type",
      "value": "current_value",
      "options": ["option1", "option2"],
      "button_info": null,
      "attributes": {
        "max_length": 40,
        "flags": 393216,
        "flag_meanings": {
          "read_only": false,
          "required": false,
          "combo": true,
          "edit": true
        }
      },
      "page": 1,
      "position": {
        "x": 165.7,
        "y": 453.7,
        "width": 150.0,
        "height": 14.2
      },
      "required": false
    }
  ],
  "field_count": 17
}
```

**Field Descriptions**:

| Field Name | Type | Description |
|------------|------|-------------|
| name | string | Field name (internal identifier) |
| label | string | Field label (user-friendly name) |
| type | string | Field type: text/checkbox/radio/select/listbox/button |
| value | string | Current field value |
| options | array | Option list (for select boxes, radio buttons) |
| button_info | object | Button information (for button types) |
| attributes | object | Field attributes (max length, flags, etc.) |
| page | integer | Page number where field is located |
| position | object | Field position information |
| required | boolean | Whether the field is required |

**Error Response**:
```json
{
  "detail": "Only PDF files are supported"
}
```

---

### 4. Fill PDF Form

**Endpoint**: `POST /api/v1/fill-form`

**Description**: Fill data into a PDF form and return a completed PDF form file

**Request Format**: `multipart/form-data`

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | File | Yes | Original PDF form file |
| form_data | string | Yes | JSON format field data |

**Request Example**:
```bash
curl --location 'http://{ip}:8000/api/v1/fill-form' \
--header 'accept: application/pdf' \
--form 'file=@"/path/to/form.pdf"' \
--form 'form_data="{\"fields\":[{\"name\":\"FullName\",\"value\":\"John Doe\"},{\"name\":\"ID\",\"value\":\"123456789\"},{\"name\":\"Gender\",\"value\":\"1\"},{\"name\":\"Married\",\"value\":\"Yes\"},{\"name\":\"City\",\"value\":\"New York\"},{\"name\":\"Language\",\"value\":\"English\"},{\"name\":\"Notes\",\"value\":\"This is a test content\"}]}"' \
--output filled_form.pdf
```

**form_data Format**:
```json
{
  "fields": [
    {
      "name": "field_name",
      "value": "field_value"
    }
  ]
}
```

**Response Format**: 
- **Content-Type**: `application/pdf`
- **Body**: Filled PDF file content
- **Filename**: `filled_{original_filename}`

**Description**: 
- The API maintains the original PDF form structure and format
- Only fills the specified fields, other fields remain unchanged
- The returned PDF file can be downloaded or saved directly

**Error Response**:
```json
{
  "detail": "Only PDF files are supported"
}
```

```json
{
  "detail": "Please provide valid form data"
}
```

---

### 5. Parse Form Fields Using fillpdf Library

**Endpoint**: `POST /api/v1/parse-form-fillpdf`

**Description**: Parse PDF form fields using the fillpdf library (simplified version)

**Request Format**: `multipart/form-data`

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| file | File | Yes | PDF file |

**Request Example**:
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form-fillpdf' \
--header 'Content-Type: application/json' \
--form 'file=@"/path/to/form.pdf"'
```

**Response Format**:
```json
{
  "success": true,
  "message": "PDF form parsing successful",
  "fields": [
    {
      "name": "field_name",
      "type": "text",
      "value": "current_value",
      "options": null,
      "button_info": null,
      "attributes": {},
      "page": 1,
      "position": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
      },
      "required": false
    }
  ],
  "field_count": 8
}
```

---

### 6. Create Sample Form

**Endpoint**: `GET /api/v1/parse-form-sample`

**Description**: Create and parse sample PDF form fields

**Request Parameters**: None

**Response Format**: Same as parse interface

---

## Field Type Details

### Text Field (text)
- **Description**: Single or multi-line text input
- **Attributes**: `max_length` - maximum character count
- **Example Values**: `"John Doe"`, `"This is a test text"`

### Checkbox (checkbox)
- **Description**: Boolean selection box
- **Valid Values**: `"Yes"`, `"No"`, `"On"`, `"Off"`
- **Example Value**: `"Yes"`

### Radio Button (radio)
- **Description**: Single option selection
- **Attributes**: `options` - available option list
- **Example Value**: `"1"` (corresponding to value in option list)

### Select Box (select)
- **Description**: Dropdown selection box
- **Attributes**: `options` - available option list
- **Example Value**: `"New York"` (corresponding to value in option list)

### List Box (listbox)
- **Description**: Multi-select list box
- **Attributes**: `options` - available option list
- **Example Value**: `["Option1", "Option2"]`

### Button (button)
- **Description**: Form button
- **Attributes**: `button_info` - button information
- **Usually not used for data filling**

## Error Codes

| HTTP Status Code | Error Type | Description |
|------------------|------------|-------------|
| 400 | Bad Request | Request parameter error (e.g., unsupported file format) |
| 500 | Internal Server Error | Server internal error |

## Usage Examples

### Complete Workflow

1. **Parse Form Fields**
```bash
curl --location 'http://{ip}:8000/api/v1/parse-form' \
--form 'file=@"/path/to/form.pdf"'
```

2. **Prepare Fill Data**
```json
{
  "fields": [
    {"name": "FullName", "value": "John Doe"},
    {"name": "ID", "value": "123456789"},
    {"name": "Gender", "value": "1"},
    {"name": "Married", "value": "Yes"},
    {"name": "City", "value": "New York"},
    {"name": "Language", "value": "English"},
    {"name": "Notes", "value": "This is a test content"}
  ]
}
```

3. **Fill Form**
```bash
curl --location 'http://{ip}:8000/api/v1/fill-form' \
--header 'accept: application/pdf' \
--form 'file=@"/path/to/form.pdf"' \
--form 'form_data="{\"fields\":[{\"name\":\"FullName\",\"value\":\"John Doe\"}]}"' \
--output filled_form.pdf
```

**Result**: Get a completed PDF form file `filled_form.pdf`

## Important Notes

1. **File Format**: Only PDF format files are supported
2. **File Size**: Maximum 50MB
3. **Field Names**: Must exactly match the field names in the PDF form
4. **Encoding**: All text data uses UTF-8 encoding
5. **Timezone**: Server uses UTC timezone

## Integration Examples

### JavaScript/Node.js
```javascript
const FormData = require('form-data');
const fs = require('fs');

// Parse form fields
const parseForm = async (pdfPath) => {
  const form = new FormData();
  form.append('file', fs.createReadStream(pdfPath));
  
  const response = await fetch('http://{ip}:8000/api/v1/parse-form', {
    method: 'POST',
    body: form
  });
  
  return await response.json();
};

// Fill form
const fillForm = async (pdfPath, fieldData) => {
  const form = new FormData();
  form.append('file', fs.createReadStream(pdfPath));
  form.append('form_data', JSON.stringify({ fields: fieldData }));
  
  const response = await fetch('http://{ip}:8000/api/v1/fill-form', {
    method: 'POST',
    body: form
  });
  
  return await response.arrayBuffer();
};
```

### Python
```python
import requests

# Parse form fields
def parse_form(pdf_path):
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        response = requests.post('http://{ip}:8000/api/v1/parse-form', files=files)
        return response.json()

# Fill form
def fill_form(pdf_path, field_data):
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        data = {'form_data': json.dumps({'fields': field_data})}
        response = requests.post('http://{ip}:8000/api/v1/fill-form', files=files, data=data)
        return response.content
```

### PHP
```php
// Parse form fields
function parseForm($pdfPath) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, 'http://{ip}:8000/api/v1/parse-form');
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, [
        'file' => new CURLFile($pdfPath)
    ]);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    
    $response = curl_exec($ch);
    curl_close($ch);
    
    return json_decode($response, true);
}

// Fill form
function fillForm($pdfPath, $fieldData) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, 'http://{ip}:8000/api/v1/fill-form');
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, [
        'file' => new CURLFile($pdfPath),
        'form_data' => json_encode(['fields' => $fieldData])
    ]);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    
    return curl_exec($ch);
}
``` 