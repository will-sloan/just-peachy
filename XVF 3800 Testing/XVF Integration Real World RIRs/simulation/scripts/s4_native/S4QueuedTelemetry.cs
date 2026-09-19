// Experimental read-only XVF 3.2.1 telemetry adapter using the supplied official
// 32-bit device_usb.dll transport. See PROTOCOL_REVIEW.md before hardware use.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;

public static class S4QueuedTelemetry
{
    [DllImport("kernel32", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern bool SetDllDirectory(string path);
    [DllImport("device_usb.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern int control_init_usb(int vendor, int product, int controlInterface);
    [DllImport("device_usb.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern int control_cleanup_usb();
    [DllImport("device_usb.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern int control_read_command(byte resource, byte command, [Out] byte[] data, UIntPtr length);
    [DllImport("command_map.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern uint get_num_commands();
    [DllImport("command_map.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern void get_cmd_id_info(out byte resource, out byte command, UIntPtr index);
    [DllImport("command_map.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern void get_cmd_val_info(out int type, out int rw, out uint count, UIntPtr index);
    [DllImport("command_map.dll", CallingConvention=CallingConvention.Cdecl)]
    private static extern IntPtr get_info_usb();

    private const int Retry = 64;
    private static readonly byte[] Resources = new byte[] {0x21, 0x21, 0x23};
    private static readonly int[] Counts = new int[] {4, 4, 2};
    // AEC: release dedicated offset 70 => 75/80. Audio selected: audio_cmds.yaml ordinal 11; AUDIO_MGR_RESID 0x23.
    // Every run cross-checks these IDs, value types, counts and read-only flags
    // against the supplied command_map.dll. No C++ std::string ABI is assumed.
    private static readonly byte[] Commands = new byte[] {75, 80, 11};
    private static readonly string[] Names = new string[] {"AEC_AZIMUTH_VALUES", "AEC_SPENERGY_VALUES", "AUDIO_MGR_SELECTED_AZIMUTHS"};
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    private static StreamWriter transactions, samples;
    private static long transactionCount, sampleCount, retries, cycleCount;
    private static long[] firstTimes, lastTimes, fieldCounts;
    private static bool[] pending = new bool[3];
    private static List<double>[] intervals;

    private static Dictionary<string, object> Obj(params object[] values)
    {
        var result = new Dictionary<string, object>();
        for (int i=0; i<values.Length; i+=2) result.Add((string)values[i], values[i+1]);
        return result;
    }
    private static string Hash(string path)
    {
        using (var file=File.OpenRead(path)) using (var sha=SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
    }
    private static long Ns(long tick)
    {
        long frequency = Stopwatch.Frequency;
        return (tick / frequency) * 1000000000L + (tick % frequency) * 1000000000L / frequency;
    }
    private static void WriteJson(string path, object value)
    {
        using (var stream = new StreamWriter(new FileStream(path, FileMode.CreateNew), new UTF8Encoding(false)))
            stream.WriteLine(Json.Serialize(value));
    }
    private static StreamWriter Writer(string path)
    {
        return new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read, 65536), new UTF8Encoding(false), 65536);
    }

    public static string Inspect(string dllDirectory)
    {
        if (IntPtr.Size != 4) throw new InvalidOperationException("Use 32-bit Windows PowerShell for the official Win32 libraries.");
        if (!SetDllDirectory(Path.GetFullPath(dllDirectory))) throw new System.ComponentModel.Win32Exception();
        uint number = get_num_commands();
        if (number == 0 || number > 5000) throw new InvalidOperationException("Invalid command map size");
        var found = new List<object>();
        bool[] verified = new bool[3];
        for (uint i=0; i<number; ++i)
        {
            byte resource, command;
            int type, rw; uint count;
            get_cmd_id_info(out resource, out command, (UIntPtr)i);
            for (int field=0; field<3; ++field) if (resource==Resources[field] && command==Commands[field])
            {
                get_cmd_val_info(out type, out rw, out count, (UIntPtr)i);
                int expectedType = field==1 ? 3 : 5;
                if (type != expectedType || rw != 0 || count != Counts[field] || verified[field])
                    throw new InvalidOperationException("Command map did not match the version-specific read-only telemetry contract");
                verified[field] = true;
                found.Add(Obj("name", Names[field], "resource", resource, "command", command,
                              "wire_read_command", command | 0x80, "type", type, "read_write_type", rw,
                              "value_count", count, "command_map_index", i));
            }
        }
        if (!verified[0] || !verified[1] || !verified[2]) throw new InvalidOperationException("Telemetry commands absent from command map");
        IntPtr info = get_info_usb();
        int triples = Marshal.ReadInt32(info);
        if (triples < 1 || triples > 8) throw new InvalidOperationException("Unexpected USB identity table");
        var identities = new List<object>(); bool identitySeen = false;
        for (int i=0; i<triples; ++i)
        {
            int vid=Marshal.ReadInt32(info, (1+i*3)*4), pid=Marshal.ReadInt32(info,(2+i*3)*4), iface=Marshal.ReadInt32(info,(3+i*3)*4);
            identities.Add(Obj("vendor_id",vid,"product_id",pid,"control_interface",iface));
            if (vid==0x20b1 && pid==0x4f00 && iface==3) identitySeen=true;
        }
        if (!identitySeen) throw new InvalidOperationException("Expected verified 48kHz XVF identity absent");
        return Json.Serialize(Obj("process_bits",32,"device_usb_sha256",Hash(Path.Combine(dllDirectory,"device_usb.dll")),
            "command_map_sha256",Hash(Path.Combine(dllDirectory,"command_map.dll")),
            "fields",found,"usb_identities",identities,"stopwatch_frequency",Stopwatch.Frequency,
            "inspection_only_no_device_initialization",true));
    }

    private static int Read(int field, long cycle, string phase, int attempt, out byte[] data, out long end)
    {
        int bytes = 1 + 4 * Counts[field];
        data = new byte[bytes];
        for (int i=0; i<data.Length; ++i) data[i]=0xcc;
        long begin = Stopwatch.GetTimestamp();
        int transport = control_read_command(Resources[field], (byte)(Commands[field] | 0x80), data, (UIntPtr)bytes);
        end = Stopwatch.GetTimestamp();
        int status = transport==0 ? data[0] : -1;
        // Compact TSV preserves every transport attempt, including retry bounds/raw bytes.
        transactions.WriteLine(String.Join("\t", new string[] {
            (transactionCount++).ToString(), cycle.ToString(), phase, field.ToString(), attempt.ToString(),
            Ns(begin).ToString(), Ns(end).ToString(), transport.ToString(), status.ToString(),
            Convert.ToBase64String(data)}));
        if (transport != 0) throw new InvalidOperationException("USB transport returned "+transport+" for "+Names[field]);
        if (status==Retry) { pending[field]=true; retries++; }
        else if (status==0) pending[field]=false;
        else throw new InvalidOperationException("Device status "+status+" for "+Names[field]);
        return status;
    }

    private static Dictionary<string,object> DecodePayload(int field, byte[] data)
    {
        if(field<0 || field>=3 || data==null || data.Length!=1+4*Counts[field] || data[0]!=0)
            throw new ArgumentException("Only a complete successful known-field response can be decoded");
        var values = new object[Counts[field]]; var finite = new bool[Counts[field]]; var reasons = new object[Counts[field]];
        for(int i=0;i<Counts[field];++i)
        {
            float value = BitConverter.ToSingle(data,1+i*4);
            finite[i] = !float.IsNaN(value) && !float.IsInfinity(value);
            values[i] = finite[i] ? (object)(double)value : null;
            reasons[i] = finite[i] ? null : (float.IsNaN(value) && field==2 && i==0
                ? "documented_no_fixed_beam_speech" : (float.IsNaN(value) ? "nonfinite_nan" : "nonfinite_infinity"));
        }
        return Obj("values",values,"finite",finite,"invalid_reasons",reasons);
    }

    public static string DecodeForTest(int field, byte[] data)
    {
        return Json.Serialize(DecodePayload(field,data));
    }

    private static void SaveSample(int field, long cycle, string phase, byte[] data, long first, long end, int attempts)
    {
        var decoded = DecodePayload(field, data);
        long stamp=Ns(end);
        var row=Obj("sequence",sampleCount++,"cycle",cycle,"phase",phase,"command",Names[field],
            "logical_request_start_monotonic_ns",Ns(first),"response_end_monotonic_ns",stamp,"attempts",attempts,
            "values",decoded["values"],"finite",decoded["finite"],"invalid_reasons",decoded["invalid_reasons"],"raw_response_base64",Convert.ToBase64String(data),
            "units",field!=1 ? "radians" : "vendor_speech_energy_units","same_device_frame_proven",false);
        samples.WriteLine(Json.Serialize(row));
        if(phase=="measurement")
        {
            if(fieldCounts[field]>0) intervals[field].Add((stamp-lastTimes[field])/1e9);
            else firstTimes[field]=stamp;
            lastTimes[field]=stamp; fieldCounts[field]++;
            // A live consumer may timestamp stdout separately. The row itself
            // carries timings measured around the official C USB transaction.
            Console.WriteLine(Json.Serialize(row));
        }
    }

    private static void Pair(long cycle, string phase, bool sequential)
    {
        bool[] complete = new bool[3];
        int[] attempts = new int[3];
        long[] first = new long[3];
        long pairStart=Stopwatch.GetTimestamp();
        for (int field=0; field<3; ++field)
        {
            first[field]=Stopwatch.GetTimestamp();
            byte[] data; long end;
            int status=Read(field,cycle,phase,++attempts[field],out data,out end);
            if(status==0)
            {
                if(phase!="warmup") throw new InvalidOperationException("Unexpected unrequested prior response; another control client may be active");
                complete[field]=true; SaveSample(field,cycle,phase,data,first[field],end,attempts[field]);
            }
            if(sequential)
            {
                while(!complete[field])
                {
                    System.Threading.Thread.Sleep(1);
                    if(attempts[field]>=1000 || (Stopwatch.GetTimestamp()-pairStart)/(double)Stopwatch.Frequency>2)
                        throw new TimeoutException("Bounded telemetry retry limit reached");
                    status=Read(field,cycle,phase,++attempts[field],out data,out end);
                    if(status==0) { complete[field]=true; SaveSample(field,cycle,phase,data,first[field],end,attempts[field]); }
                }
            }
        }
        while(!complete[0] || !complete[1] || !complete[2])
        {
            System.Threading.Thread.Sleep(1);
            for(int field=0;field<3;++field) if(!complete[field])
            {
                if(attempts[field]>=1000 || (Stopwatch.GetTimestamp()-pairStart)/(double)Stopwatch.Frequency>2)
                    throw new TimeoutException("Bounded telemetry retry limit reached");
                byte[] data;long end;int status=Read(field,cycle,phase,++attempts[field],out data,out end);
                if(status==0) { complete[field]=true; SaveSample(field,cycle,phase,data,first[field],end,attempts[field]); }
            }
        }
    }

    public static int Run(string dllDirectory, string outputDirectory, double seconds, bool sequential, string stopFile, double rateHz)
    {
        if (double.IsNaN(rateHz)||double.IsInfinity(rateHz)||rateHz<1||rateHz>30) throw new ArgumentException("Rate must be 1..30 Hz per field");
        if(double.IsNaN(seconds)||double.IsInfinity(seconds)||seconds<=0||seconds>3600) throw new ArgumentException("Duration must be 0..3600 seconds");
        string inspection=Inspect(dllDirectory); // Loads libraries and validates metadata; no USB call.
        if(Directory.Exists(outputDirectory)) throw new IOException("Output directory already exists");
        Directory.CreateDirectory(outputDirectory);
        WriteJson(Path.Combine(outputDirectory,"command_map_inspection.json"),Json.DeserializeObject(inspection));
        transactions=Writer(Path.Combine(outputDirectory,"transactions.tsv"));
        samples=Writer(Path.Combine(outputDirectory,"samples.jsonl"));
        transactions.WriteLine("sequence\tcycle\tphase\tfield_index\tattempt\trequest_start_monotonic_ns\tresponse_end_monotonic_ns\ttransport_return\tdevice_status\traw_response_base64");
        transactionCount=sampleCount=retries=cycleCount=0;
        firstTimes=new long[3];lastTimes=new long[3];fieldCounts=new long[3];pending=new bool[3];
        intervals=new List<double>[] {new List<double>(),new List<double>(),new List<double>()};
        bool opened=false, stopped=false;int cleanup=-1;string error=null;
        long start=0,end=0; string startUtc=DateTime.UtcNow.ToString("o");
        try
        {
            int init=control_init_usb(0x20b1,0x4f00,3);
            if(init!=0) throw new InvalidOperationException("Official USB initialization returned "+init);
            opened=true;
            Pair(-1,"warmup",sequential); // Drain any outstanding read left by an earlier terminated batch.
            start=Stopwatch.GetTimestamp();
            while((Stopwatch.GetTimestamp()-start)/(double)Stopwatch.Frequency < seconds)
            {
                if(!String.IsNullOrEmpty(stopFile)&&File.Exists(stopFile)) {stopped=true;break;}
                long cycleBegin=Stopwatch.GetTimestamp();
                Pair(cycleCount,"measurement",sequential);cycleCount++;
                double remaining=1.0/rateHz-(Stopwatch.GetTimestamp()-cycleBegin)/(double)Stopwatch.Frequency;
                if(remaining>0) System.Threading.Thread.Sleep(Math.Max(1,(int)Math.Ceiling(remaining*1000)));
            }
        }
        catch(Exception exception) {error=exception.ToString();}
        finally
        {
            end=Stopwatch.GetTimestamp();
            if(opened)
            {
                // Only drain already-pending known reads. Never enqueue a fresh
                // cleanup read. A transport failure leaves the evidence invalid.
                long drainStart=Stopwatch.GetTimestamp();
                try
                {
                    for(int field=0;field<3;++field)
                    {
                        int attempt=0;
                        while(pending[field] && ++attempt<1000 && (Stopwatch.GetTimestamp()-drainStart)/(double)Stopwatch.Frequency<2)
                        {byte[] data;long tick;Read(field,cycleCount,"cleanup",attempt,out data,out tick);}
                    }
                }
                catch(Exception exception) {error=(error??"")+"\nCleanup: "+exception;}
                cleanup=control_cleanup_usb();
            }
            transactions.Dispose(); samples.Dispose();
        }
        var fields=new Dictionary<string,object>();
        for(int field=0;field<3;++field)
        {
            intervals[field].Sort();var v=intervals[field];int n=v.Count;
            fields.Add(Names[field],Obj("count",fieldCounts[field],"mean_arrival_rate_hz",
                fieldCounts[field]>1 ? (object)((fieldCounts[field]-1)*1e9/(lastTimes[field]-firstTimes[field])):null,
                "interval_median_s",n>0?(object)v[n/2]:null,"interval_p95_s",n>0?(object)v[(int)Math.Floor((n-1)*.95)]:null,
                "interval_max_s",n>0?(object)v[n-1]:null));
        }
        bool passed=error==null && cleanup==0 && !pending[0] && !pending[1] && !pending[2] && cycleCount>0 && fieldCounts[0]==cycleCount && fieldCounts[1]==cycleCount && fieldCounts[2]==cycleCount;
        var result=Obj("status",passed?"PASS":"FAIL","mode",sequential?"sequential_official_transport":"queued_distinct_reads",
            "start_utc",startUtc,"measurement_start_monotonic_ns",start==0?0:Ns(start),"measurement_end_monotonic_ns",Ns(end),
            "measurement_elapsed_s",start==0?0:(end-start)/(double)Stopwatch.Frequency,"requested_seconds",seconds,"requested_rate_hz_per_field",rateHz,"retry_poll_minimum_sleep_ms",1,
            "stop_file_requested",stopped,"completed_cycles",cycleCount,"transactions",transactionCount,"retry_responses",retries,
            "cleanup_return",cleanup,"pending_reads_at_exit",pending,"error",error,"per_field",fields,
            "timing_semantics","Host QPC transaction bounds around official C transport; no device timestamp, fresh-frame counter or atomic paired-frame guarantee.",
            "stopwatch_frequency",Stopwatch.Frequency,"no_firmware_or_parameter_writes",true);
        WriteJson(Path.Combine(outputDirectory,"result.json"),result);
        Console.WriteLine(Json.Serialize(result));
        return passed?0:1;
    }
}
