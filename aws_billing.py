#!/usr/bin/env python3
import boto3
import json
from datetime import datetime, timedelta

# Initialize the Cost Explorer client
ce = boto3.client('ce')

# Get current month's date range
total_cost = 0
today = datetime.now()
start_date = today.replace(day=1).strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')

# Get cost and usage
response = ce.get_cost_and_usage(
    TimePeriod={
        'Start': start_date,
        'End': end_date
    },
    Granularity='MONTHLY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {
            'Type': 'DIMENSION',
            'Key': 'SERVICE'
        }
    ]
)

# Parse and display results
print(f"\n{'='*60}")
print(f"AWS Billing Report: {start_date} to {end_date}")
print(f"{'='*60}\n")

for result in response['ResultsByTime']:
    # Sort services by cost (highest first)
    services = sorted(result['Groups'], 
                     key=lambda x: float(x['Metrics']['UnblendedCost']['Amount']), 
                     reverse=True)
    
    # Display each service
    for service in services:
        service_name = service['Keys'][0]
        cost = float(service['Metrics']['UnblendedCost']['Amount'])
        if cost > 0.01:  # Only show services with cost > $0.01
            print(f"  • {service_name:40} ${cost:>10.2f}")
            total_cost += cost
    
    # Display total
    # if 'Total' not in result.keys() or 'UnblendedCost' not in result['Total'].keys() or 'Amount' not in result['Total']['UnblendedCost'].keys():
        # print(f"\n{'-'*60}")
        # exit()
    # total_cost = float(result['Total']['UnblendedCost']['Amount'])
    print(f"\n{'-'*60}")
    print(f"  {'TOTAL MONTHLY COST':<40} ${total_cost:>10.2f}")
    print(f"{'-'*60}\n")
