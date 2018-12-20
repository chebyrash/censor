# API

## Method
    POST https://censor.yablach.co/
    
## Supported Media Formats

Name | Type
---- | ----
JPEG | Image
PNG  | Image
WEBM | Video
MP4 | Video
GIF | Video

## Example Request
  ```json
  {
    "..." : "...",
    "url": "string",
    "headers" : {},
    "cookies" : {}
  }
  ```

## Example Response
  ```json
  {
    "..." : "...",
    "url": "string",
    "headers" : {},
    "cookies" : {},
    "censor": true
  }
  ```
