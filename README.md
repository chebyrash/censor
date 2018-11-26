# API

## Method
    POST https://censor.yablach.co/

## Example Request
  ```json
  {
    "..." : "...",
    "image": "https://2ch.hk/X/src/XXX/XXX.png",
    "headers" : {
      "...": "..."
    },
    "cookies" : {
      "usercode_auth": "..."
    }
  }
  ```

## Example Response
  ```json
  {
    "..." : "...",
    "image": "https://2ch.hk/X/src/XXX/XXX.png",
    "headers" : {
      "...": "..."
    },
    "cookies" : {
      "usercode_auth": "..."
    },
    "censor": true
  }
  ```
