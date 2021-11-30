import smtplib, ssl
import os
from twilio.rest import Client as TWCLIENT
import pandas as pd
import sys
# Your Account Sid and Auth Token from twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = 'AC33411731e2cd51e929d879e88674f07a'
auth_token = 'ccf1881659ff23cc3200d80d97418e61'

def send_sms(message):
    twilio_client = TWCLIENT(account_sid, auth_token)

    send_message = twilio_client.messages.create(
        body=str('-\n\n' + str(message)),
        from_='+12262707876',
        to='+19054073719'
    )


email = "bloisserver@gmail.com"
password = "jtjzdovjulturnxv"

port = 465

receiver_email = "ericblois291@gmail.com"

def send_mail(subject, message):
    # Create a secure SSL context
    context = ssl.create_default_context()

    server = smtplib.SMTP_SSL("smtp.gmail.com", port, context=context)
    server.login(email, password)

    mail = f"Subject: {subject}\n\n{message}"

    server.sendmail(email, receiver_email, mail)

    server.quit()

def get_csv_log(filename):
    return pd.read_csv(filename)

def save_csv_log(filename, dataframe):
    dataframe.to_csv(filename, index=False)

def add_df_row(row, dataframe):
    num_rows = len(dataframe.index)
    dataframe.loc[num_rows] = row