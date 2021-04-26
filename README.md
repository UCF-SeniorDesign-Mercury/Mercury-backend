# Mercury Backend

This backend is created using flask and is still in development and for local testing. 

## Setup
**Installing virtual environment**

On macOS and Linux
```
python3 -m pip install --user virtualenv
```
 
on Windows
```
py -m pip install --user virtualenv
```

**Creating a virtual environment**

On macOS and Linux
```
python3 -m venv env
```

on Windows
```
py -m venv env
```

**Activating a virtual environment**

On macOS and Linux
```
source env/bin/activate
```

on Windows
```
.\env\Scripts\activate
```

**Installing the packages**
```
pip3 install -r requirements.txt
```

**Running the application**
```
python app.py
```

## Additional Setup
For testing locally, you will have to change the host IP in app.py (line 392) to your PC's static ip. You will have to do some custom adjustments in helpers.py as well.
Refer to this [video](https://www.youtube.com/watch?v=Bg9r_yLk7VY&list=LL&index=62&t=601s&ab_channel=DevEd) for what to fill in for the send emails in helpers.py.


