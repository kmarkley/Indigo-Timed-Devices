# Timed Devices
This plugin creates Indigo devices that are essentially timers with built-in triggers.  The goal is to make some common tasks in Indigo simpler to setup, easier to maintain, and requiring fewer Indigo entities.

This plugin doesn't do anything that can't be accomplished in Indigo with a combination of Triggers, Variables, and Timers and/or Delayed Actions.  However, I find it very helpful in accomplishing those things quickly and simply.  I have seen a number of new users on the forums struggle with these sorts of tasks, and hope this may be useful to them as well.

## Device Descriptions

#### Activity Timer devices

These devices infer an ongoing ***activity*** from one or more _momentary_ inputs.  The device will expire (turn off) after a defined period of time with no additional inputs.

Once configured, these devices are simply ON to indicate recent activity and OFF to indicate no recent activity.

The most common use is inferring activity in a room or area by tracking motion sensors.  I commonly wish to have more than one motion sensor activate before assuming a room is in use, and extend the timeout when one or more motion sensors are re-activated.

I first wrote the plugin for this scenario and in one case was able to replace 13 indigo entities (2 variables, 2 timers, and 9 triggers) with a single plugin device.

#### Persistence Timer devices

These devices track the state of a single device or variable, but only change state after the tracked entity state has ***persisted*** for a defined period of time.  At the end of the lockout period, the plugin will reevaluate if the tracked entity has changed in the interim, and initiate another lockout period if it has.

Once configured, these devices are just ON or OFF to reflect the delayed/confirmed state of some other device or variable (eliminating the need for possibly several cancel-delayed-action actions).

An obvious example is the if you want to track if a door has been left open (or closed), but ignore the door being opened (or closed) momentarily.

#### Lockout Timer devices

These devices track a single device or variable and change state immediately when the tracked entity changes, but will ***lockout*** (ignore) subsequent changes for a user-defined period of time.

Once configured, these devices are just ON or OFF to reflect the state of some other device or variable, but are guaranteed not to change more often than some pre-set period of time (allowing your triggered actions to complete before, say, reversing themselves).

Not sure there is an obvious example for this, but I do find it useful in a few situations, especially when I don't want on/off triggers to fire too close together.

#### Alive Timer devices

These devices track whether single device or variable is ***alive*** and becomes OFF when the tracked entity hasn't changed for a user-defined period of time.

Once configured, these devices are just ON or OFF to reflect whether or not some other device or variable has been seen within some pre-set period of time.

The obvious use is battery-powered devices like sensors.  Unlike the other device types, these will react to heartbeats even if none of device's states have changed value.

## Plugin configuration

* **Show Timer**
    * Check have Indigo display a countdown timer for each device when appropriate.
    * Uncheck to reduce the communication overhead between Indigo and the plugin.


* **Enable Debugging**
    * Check to log basic debugging information to the Indigo event log.


* **Verbose Debugging**
    * Check to log extensive debugging information to the Indigo event log.  If 'Show Timers' is set, this will include multiple log entries every second.

## Activity Timer devices

#### Configuration

* **Threshold**  
The number of momentary inputs before the device turns on.
* **Reset Cycles** and **Reset Units**  
How long before the device gives up and starts over counting inputs from zero.
* **Off Cycles** and **Off Units**  
How long before the device turns off when there are no additional inputs.
* **Always Extend**  
When checked, the expire time will reset with _every_ additional input.  When unchecked, the expire time will only be extended when the **threshold** is met.
* **Device N** and **State N**  
Select devices and their associated states to track as inputs for the device.
* **Variable N**  
Select variables to track as inputs for the device.
* **Logic**
    * **Any**: any change to device states or variable value is considered an input.
    * **Simple**: device states or variable values that can be understood as true/false are considered inputs.
        * **Reverse?**  
        Reverse the logic.  I.e. consider False values as inputs.
    * **Complex**: provide specific comaparison logic to determine what is considered an input.
        * **Operator**  
        The operator used to compare device states and variable values to a reference value.
        * **Comparison**  
        The reference value for comparison.
        * **Data Type**  
            * **String**: compare as strings.
            * **Number**: compare as number (float)
* **Log On/Off**  
Choose whether or not to log device on/off changes to the Indigo event log.

#### States

* **count** (int): current count toward **threshold**.
* **counting** (bool): whether the device is acquiring inputs toward **threshold**.
* **displayState** (str): state to display in indigo client interface.
* **expired** (bool): true when device expires (as opposed to being forced off).
* **offString** (str): timestamp of scheduled expiration.
* **offTime** (float): epoch time of scheduled expiration.
* **onOffState** (bool): whether the device is on or off.
* **reset** (bool): true when the device stops counting inputs and resets the counter.
* **resetString** (str): timestamp of schedule reset.
* **resetTime** (float): epoch time of scheduled reset.
* **state** (enum): one of
    * **idle**: nothing is happening.
    * **accrue**: device is counting up to **threshold**.
    * **active**: device is on and still counting inputs.
    * **persist**: device is waiting to either expire or receive more inputs.

## Persistence Timer devices

#### Configuration

* **ON Persist Cycles** and **ON Persist Units**  
How long a tracked device/variable must be on/true before plugin device turns on.
* **OFF Persist Cycles** and **OFF Persist Unites**  
How long a tracked device/variable must be off/false before plugin device turns off.
* **Track**  
Choose whether to track a device state or variable value.
    * **Device** and **State**  
    Choose a device and state to track.
    * **Variable**  
    Choose a variable to track.
* **Logic**
    * **Simple**: device states or variable values that can be understood as true/false are considered inputs.
        * **Reverse?**  
        Reverse the logic.  I.e. consider False values as inputs.
    * **Complex**: provide specific comaparison logic to determine what is considered an input.
        * **Operator**  
        The operator used to compare device states and variable values to a reference value.
        * **Comparison**  
        The reference value for comparison.
        * **Data Type**  
            * **String**: compare as strings.
            * **Number**: compare as number (float)
* **Log On/Off**  
Choose whether or not to log device on/off changes to the Indigo event log.

#### States

* **displayState** (str): state to display in indigo client interface.
* **offString** (str): timestamp of scheduled off.
* **offTime** (float): epoch time of scheduled off.
* **onOffState** (bool): whether the device is on or off.
* **onString** (str): timestamp of scheduled on.
* **onTime** (float): epoch time of scheduled on.
* **pending** (bool): true when tracked device/variable has changed and plugin device is waiting to also change.
* **state** (enum): one of
    * **on**: the tracked device/variable and plugin device are both on.
    * **off**: the tracked device/variable and plugin device are both off.
    * **pending**: the tracked device/variable has changed and plugin device is waiting to also change.

## Lockout Timer devices

#### Configuration

* **ON Lockout Cycles** and **ON Lockout Units**  
How long after turning ON before plugin device may turn back OFF.
* **OFF Lockout Cycles** and **OFF Lockout Unites**  
How long after turning OFF before plugin device may turn back ON.
* **Track**  
Choose whether to track a device state or variable value.
    * **Device** and **State**  
    Choose a device and state to track.
    * **Variable**  
    Choose a variable to track.
* **Logic**
    * **Simple**: device states or variable values that can be understood as true/false are considered inputs.
        * **Reverse?**  
        Reverse the logic.  I.e. consider False values as inputs.
    * **Complex**: provide specific comaparison logic to determine what is considered an input.
        * **Operator**  
        The operator used to compare device states and variable values to a reference value.
        * **Comparison**  
        The reference value for comparison.
        * **Data Type**  
            * **String**: compare as strings.
            * **Number**: compare as number (float)
* **Log On/Off**  
Choose whether or not to log device on/off changes to the Indigo event log.

#### States

* **displayState** (str): state to display in indigo client interface.
* **locked** (bool): whether the plugin device is locked out.
* **offString** (str): timestamp of off lockout expiration.
* **offTime** (float): epoch time of off lockout expiration.
* **onOffState** (bool): whether the device is on or off.
* **onString** (str): timestamp of on lockout expiration.
* **onTime** (float): epoch time of on lockout expiration.
* **state** (enum): one of
    * **on**: the tracked device/variable and plugin device are both on.
    * **off**: the tracked device/variable and plugin device are both off.
    * **locked**: the plugin device is prevented from changing state until the timer expires.

## Alive Timer devices

#### Configuration

* **Alive Cycles** and **Alive Unites**  
Inactive period before device turns off.
* **Track**  
Choose whether to track a device state or variable value.
    * **Device**  
    Choose a device to track.
    * **Variable**  
    Choose a variable to track.
* **Log On/Off**  
Choose whether or not to log device on/off changes to the Indigo event log.

#### States

* **displayState** (str): state to display in indigo client interface.
* **offString** (str): timestamp of off lockout expiration.
* **offTime** (float): epoch time of off lockout expiration.
* **onOffState** (bool): whether the device is on or off.
* **state** (enum): one of
    * **on**: the tracked device/variable is alive.
    * **off**: the tracked device/variable is not alive.

## Actions

#### Force Timed Device Off
Force the plugin device to become off.  
Related timers (expire, lockout) will be started.  
For **Activity Timer** devices, **reset** and **expired** states will become/remain true.

#### Force Timed Device On
Force the plugin device to become on.  
Related timers (expire, lockout) will be started.
