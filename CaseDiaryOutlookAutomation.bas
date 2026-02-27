Option Explicit

'============================================================
' Case diary automation:
' Reads entries from Sheet1 and creates Outlook appointments.
'------------------------------------------------------------
' Sheet1 columns:
'   A = Case Name and Number      -> Appointment.Subject
'   B = Court                     -> Appointment.Location
'   C = Next Date (DD/MM/YYYY)    -> Appointment.Start (date part)
'   D = Start Time                -> Appointment.Start (time part)
'   E = Description               -> Appointment.Body
'============================================================
Public Sub CreateCaseDiaryCalendarEvents()
    Const SHEET_NAME As String = "Sheet1"
    Const START_ROW As Long = 2
    Const APPT_ITEM As Long = 1           ' Outlook.OlItemType.olAppointmentItem
    Const OL_FOLDER_CALENDAR As Long = 9  ' Outlook.OlDefaultFolders.olFolderCalendar

    Dim ws As Worksheet
    Dim lastRow As Long
    Dim r As Long

    Dim outlookApp As Object      ' Late binding: Outlook.Application
    Dim outlookNs As Object       ' Late binding: Outlook.Namespace
    Dim calendarFolder As Object  ' Late binding: Outlook.MAPIFolder
    Dim appt As Object            ' Late binding: Outlook.AppointmentItem

    Dim caseSubject As String
    Dim courtLocation As String
    Dim caseBody As String

    Dim parsedDate As Date
    Dim parsedTime As Date
    Dim startDateTime As Date

    Dim createdCount As Long
    Dim skippedBlankDate As Long
    Dim skippedInvalidDate As Long
    Dim skippedInvalidTime As Long

    Dim prevCalcMode As XlCalculation

    On Error GoTo CleanFail

    '------------------------------
    ' Performance settings in Excel
    '------------------------------
    prevCalcMode = Application.Calculation
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual

    Set ws = ThisWorkbook.Worksheets(SHEET_NAME)

    ' Find last row based on the furthest used row in columns A:E.
    lastRow = Application.Max( _
        ws.Cells(ws.Rows.Count, "A").End(xlUp).Row, _
        ws.Cells(ws.Rows.Count, "B").End(xlUp).Row, _
        ws.Cells(ws.Rows.Count, "C").End(xlUp).Row, _
        ws.Cells(ws.Rows.Count, "D").End(xlUp).Row, _
        ws.Cells(ws.Rows.Count, "E").End(xlUp).Row)

    If lastRow < START_ROW Then
        MsgBox "No case diary rows found to process.", vbInformation, "Case Diary Automation"
        GoTo CleanExit
    End If

    '--------------------------------------
    ' Start Outlook using late binding only
    '--------------------------------------
    Set outlookApp = GetOutlookApp()
    If outlookApp Is Nothing Then
        MsgBox "Outlook could not be started. Please open Outlook and try again.", vbExclamation, "Case Diary Automation"
        GoTo CleanExit
    End If

    Set outlookNs = outlookApp.GetNamespace("MAPI")
    Set calendarFolder = outlookNs.GetDefaultFolder(OL_FOLDER_CALENDAR)

    '----------------------------
    ' Process each diary row
    '----------------------------
    For r = START_ROW To lastRow
        caseSubject = Trim$(CStr(ws.Cells(r, "A").Value))
        courtLocation = Trim$(CStr(ws.Cells(r, "B").Value))
        caseBody = CStr(ws.Cells(r, "E").Value)

        ' Skip if Next Date is blank.
        If Len(Trim$(CStr(ws.Cells(r, "C").Value))) = 0 Then
            skippedBlankDate = skippedBlankDate + 1
            GoTo NextRow
        End If

        ' Parse date from column C (expects DD/MM/YYYY).
        If Not TryParseDateDMY(ws.Cells(r, "C").Value, parsedDate) Then
            skippedInvalidDate = skippedInvalidDate + 1
            GoTo NextRow
        End If

        ' Parse start time from column D.
        If Not TryParseTime(ws.Cells(r, "D").Value, parsedTime) Then
            skippedInvalidTime = skippedInvalidTime + 1
            GoTo NextRow
        End If

        startDateTime = DateSerial(Year(parsedDate), Month(parsedDate), Day(parsedDate)) + _
                        TimeSerial(Hour(parsedTime), Minute(parsedTime), 0)

        ' Create appointment item in default calendar.
        Set appt = calendarFolder.Items.Add(APPT_ITEM)

        With appt
            .Subject = caseSubject
            .Location = courtLocation
            .Start = startDateTime
            .Duration = 60
            .Body = caseBody
            .ReminderSet = True
            .ReminderMinutesBeforeStart = 60
            .Save
        End With

        createdCount = createdCount + 1

NextRow:
        Set appt = Nothing
    Next r

    MsgBox "Processing complete." & vbCrLf & vbCrLf & _
           "Appointments created: " & createdCount & vbCrLf & _
           "Skipped (blank date): " & skippedBlankDate & vbCrLf & _
           "Skipped (invalid date): " & skippedInvalidDate & vbCrLf & _
           "Skipped (invalid time): " & skippedInvalidTime, _
           vbInformation, "Case Diary Automation"

CleanExit:
    '----------------------------
    ' Restore Excel application state
    '----------------------------
    Application.Calculation = prevCalcMode
    Application.EnableEvents = True
    Application.ScreenUpdating = True

    Set appt = Nothing
    Set calendarFolder = Nothing
    Set outlookNs = Nothing
    Set outlookApp = Nothing
    Set ws = Nothing
    Exit Sub

CleanFail:
    MsgBox "Unexpected error " & Err.Number & ": " & Err.Description, vbExclamation, "Case Diary Automation"
    Resume CleanExit
End Sub

'============================================================
' GetOutlookApp
' Returns a running Outlook instance, or creates one if needed.
'============================================================
Private Function GetOutlookApp() As Object
    On Error Resume Next
    Set GetOutlookApp = GetObject(, "Outlook.Application")
    If GetOutlookApp Is Nothing Then
        Set GetOutlookApp = CreateObject("Outlook.Application")
    End If
    On Error GoTo 0
End Function

'============================================================
' TryParseDateDMY
' Safely parse date values, prioritizing DD/MM/YYYY text input.
' Returns True if parsed, False otherwise.
'============================================================
Private Function TryParseDateDMY(ByVal rawValue As Variant, ByRef outDate As Date) As Boolean
    Dim s As String
    Dim parts() As String
    Dim d As Long
    Dim m As Long
    Dim y As Long

    On Error GoTo Fail

    ' If Excel already stores a serial date, accept directly.
    If IsDate(rawValue) And IsNumeric(rawValue) Then
        outDate = CDate(rawValue)
        TryParseDateDMY = True
        Exit Function
    End If

    s = Trim$(CStr(rawValue))
    If Len(s) = 0 Then GoTo Fail

    s = Replace$(s, "-", "/")
    parts = Split(s, "/")
    If UBound(parts) <> 2 Then GoTo Fail

    d = CLng(Val(parts(0)))
    m = CLng(Val(parts(1)))
    y = CLng(Val(parts(2)))

    outDate = DateSerial(y, m, d)

    ' Validate exact match (guards against DateSerial overflow normalization).
    If Day(outDate) <> d Or Month(outDate) <> m Or Year(outDate) <> y Then GoTo Fail

    TryParseDateDMY = True
    Exit Function

Fail:
    TryParseDateDMY = False
End Function

'============================================================
' TryParseTime
' Safely parse time values from Excel time serial or text input.
' Returns True if parsed, False otherwise.
'============================================================
Private Function TryParseTime(ByVal rawValue As Variant, ByRef outTime As Date) As Boolean
    Dim s As String

    On Error GoTo Fail

    If IsDate(rawValue) Then
        outTime = CDate(rawValue)
        TryParseTime = True
        Exit Function
    End If

    s = Trim$(CStr(rawValue))
    If Len(s) = 0 Then GoTo Fail

    outTime = TimeValue(s)
    TryParseTime = True
    Exit Function

Fail:
    TryParseTime = False
End Function
