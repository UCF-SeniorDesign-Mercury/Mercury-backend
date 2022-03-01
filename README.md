# Mercury Backend

This backend is created using Flask and is still in development and for local testing.

## Setup

**Installing the packages**

The project requires poetry (version >= 1.1.12). Installation instructions: [_link_](https://python-poetry.org/docs/#installation)

```
poetry install
```

**Running the application**

```
poetry run
```

## Documentation

To see the documentation for the API, you need to run the application and go to `http://localhost:5000/apidocs/`. There you will see a Swagger UI, which provides all documentation and an opportunity to test some of the endpoints.

## Additional Setup

**For sending email in /inviteRole**
For testing locally, you will have to change the host IP in app.py (line 392) to your PC's static ip. You will have to do some custom adjustments in helpers.py as well.
Refer to this [video](https://www.youtube.com/watch?v=Bg9r_yLk7VY&list=LL&index=62&t=601s&ab_channel=DevEd) for what to fill in for the send emails in helpers.py.

**Firebase project**
Add keys from `key.json` to the `.env` file.
