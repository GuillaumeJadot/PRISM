## PRISM website ##

This repo will generate a container including libs + code.

The external data is accessible from inside this container in /srv/data.

This data can be accessed and modified in /export/students/gujadot/website.


## PRISM app (devel) ##

Environmental factors Analysis Web Application
Project Overview
This project aims to create a web application that allows users to analyze environmental risks and pollution levels at specific locations using geospatial data. The app integrates various data layers and raster files to provide insights into flood risks, organic and inorganic pollution, and other environmental factors.


The repository includes a Flask application, geospatial analysis scripts, and a web interface.

Getting Started
These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

Prerequisites
Ensure you have Python 3.8 or later installed. The application is developed using Flask, a Python web framework, and relies on numerous geospatial Python libraries.

In order to run the models:
1. Clone the repository or download the source code.
2. Open your terminal
3. Create a new conda environment:
> conda create --name LBIRE2234_group2_Domiscore python=3.8
> conda activate LBIRE2234_group2_Domiscore

4. Navigate to the project directory and install the required dependencies using pip:
> cd repository
> pip install -r requirements.txt

5.Running the Scripts
Run the following command in the terminal to execute the main script:
> python app.py
Access the web application by navigating to http://127.0.0.1:5000/ in your web browser.

6.Usage
The web interface allows you to input coordinates or an address to analyze. The results, along with an interactive map, will be displayed on the page.

## Authors ##
Guillaume Jadot - Initial work

