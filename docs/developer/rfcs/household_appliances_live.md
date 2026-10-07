# Household Appliances Auto Notifier

An implementation of [Auto Notifier](./auto_notifier.md) to use *Live Activities* for common household appliances, such as dishwashers, robot vacuums, ovens and washing machines.

Although this component aims to make full use of Supernotifier available to a wider group of people with minimal effort, the primary aim is to make household appliances integrate smoothly into everyday handheld and voice devices.

This will include 'smart' appliances with their own network connections, and simpler appliances that have smart plugs to monitor them. The latter may in time be made further smarter by using previous behaviour to predict run times.

## Beyond Basic Cycles

It is also possible that energy monitoring may become part of this, so that an appliance cycle ends with an estimate of cost.

Actions to stop, pause or otherwise alter the cycle are impossible to unpick from notifications, since the actions to do this make sense to be on the mobile push notification itself.

Aside from the everyday appliance cycles, longer term events like maintenance or firmware updates will also have notification needs.

## Other Considerations

One complication is where vendors, or other official / HACS providers integrate notification into their own appliance support. This could mean double notifications, or inconsistent experience across appliances.
